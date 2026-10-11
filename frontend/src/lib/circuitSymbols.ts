/**
 * Circuit symbol "stamps" for the whiteboard. A drawing aid, nothing more: it makes ordinary strokes in the
 * existing `Stroke` shape (kinds `path`, `arrow` and `text`), so persistence, replay, the canvas renderer and the
 * vision critique all work unchanged. Nothing here checks a circuit electrically.
 *
 * Pure: no React, no DOM, no canvas, no network. Imports only a type.
 *
 * Coordinates are board coordinates: x 0..900, y 0..540, y down, like `board.ts`. Rotation is clockwise.
 *
 * Never throws. Odd input gives either a valid result or an empty one:
 *   - `placeStamp`/`stamp` return null/[] for an unknown kind, a non-finite `at`, or (wire) a missing or non-finite `to`;
 *   - a bad rotation becomes 0, a bad scale becomes 1, a scale outside 0.5..4 is clamped;
 *   - a symbol that would cross an edge is shifted whole (never deformed), because `at` is only a request;
 *     a wire is the exception: its ends are clamped to the board, since moving it would detach it from its terminals.
 * Every returned stroke satisfies the server's `Stroke` limits (id 1..100 chars, 1..10000 points, x/y inside the
 * board and finite, pressure 0..1, label at most 200 chars).
 *
 * Ids: `stp-<code>-<token>-<n>`. All strokes of one stamp share `stp-<code>-<token>`, which is what
 * `groupByStamp`, `stampPrefix` and `undoIds` use to remove a whole stamp with one `remove_strokes` note.
 *
 * What a model reading the stroke list sees: every path/arrow stroke has a `label` such as `resistor R1 330Ω`
 * or `LED D1 [anode side]`; the optional visible label is a separate `text` stroke whose `label` is exactly the
 * text drawn on the canvas (for example `R1 330Ω`).
 */
import type { Stroke } from '../api/client';

export const BOARD_WIDTH = 900;
export const BOARD_HEIGHT = 540;
/** The dot grid that `drawStrokes` paints. */
export const GRID = 30;
/** Distance between the two terminals of a two-terminal symbol at scale 1: three grid cells. */
export const TERMINAL_SPAN = 90;
export const MIN_SCALE = 0.5;
export const MAX_SCALE = 4;
/** The drawn label is cut to this many characters. */
export const MAX_VISIBLE_LABEL = 60;
const MAX_STROKE_LABEL = 200;
const PRESSURE = 0.5;
// An estimate for 12px system-ui, only used to keep a label from running off the right edge. No canvas here to measure.
const TEXT_WIDTH_PER_CHAR = 7;
const TEXT_ASCENT = 12;
const TEXT_DESCENT = 3;

export type SymbolKind = 'resistor' | 'capacitor' | 'led' | 'diode' | 'supply' | 'ground' | 'switch' | 'junction' | 'wire';
export const SYMBOL_KINDS: readonly SymbolKind[] = ['resistor', 'capacitor', 'led', 'diode', 'supply', 'ground', 'switch', 'junction', 'wire'];

export type IdFactory = () => string;
export type PointLike = { x: number; y: number; pressure?: number };
export type Terminal = { name: string; x: number; y: number; /** the stamp's shared id prefix */ stamp: string };
export type Route = 'straight' | 'horizontal-first' | 'vertical-first';

export interface StampOptions {
  /** Degrees, rounded to the nearest multiple of 90. Default 0. */
  rotation?: number;
  /** Size multiplier, 0.5..4. Default 1. */
  scale?: number;
  /** Text drawn next to the symbol, for example `R1 330Ω`. At most 60 characters, whitespace collapsed. */
  label?: string;
  /** Called once per stamp for its unique token. Letters, digits and underscores are kept, at most 40. Default: `defaultId`. */
  ids?: IdFactory;
  /** Land the first terminal on the 30 px grid (the second too when 90 × scale is a multiple of 30). Default false. */
  snapToGrid?: boolean;
  /** Switch only: draw it closed. Default open. */
  closed?: boolean;
  /** Wire only: the other end. Without it a wire is not drawn. */
  to?: PointLike;
  /** Wire only. Default `straight`. An elbow route has one right angle, or none if the ends line up. */
  route?: Route;
}

export interface Placed {
  kind: SymbolKind;
  /** `stp-<code>-<token>`, shared by every stroke of the stamp. */
  prefix: string;
  strokes: Stroke[];
  terminals: Terminal[];
}

type Pt = readonly [number, number];
type Piece = { kind: 'path' | 'arrow'; pts: Pt[]; role?: string };
type Spec = { name: string; pieces: Piece[]; notes: { at: Pt; text: string }[] };
type Ref = { name: string; piece: number; end: 'first' | 'last' | 'center' };

const CODES: Record<SymbolKind, string> = {
  resistor: 'res', capacitor: 'cap', led: 'led', diode: 'dio', supply: 'sup', ground: 'gnd', switch: 'swi', junction: 'jun', wire: 'wir',
};
// Where each stamp's terminals are, by piece (stroke) index and end. One table serves both stamping and recovering
// terminals from saved strokes, so the two cannot disagree.
const TERMINAL_REFS: Record<string, Ref[]> = {
  res: [{ name: 'a', piece: 0, end: 'first' }, { name: 'b', piece: 0, end: 'last' }],
  cap: [{ name: 'a', piece: 0, end: 'first' }, { name: 'b', piece: 1, end: 'first' }],
  dio: [{ name: 'anode', piece: 0, end: 'first' }, { name: 'cathode', piece: 1, end: 'last' }],
  led: [{ name: 'anode', piece: 0, end: 'first' }, { name: 'cathode', piece: 1, end: 'last' }],
  sup: [{ name: 'minus', piece: 0, end: 'first' }, { name: 'plus', piece: 1, end: 'first' }],
  gnd: [{ name: 'ground', piece: 0, end: 'first' }],
  swi: [{ name: 'a', piece: 0, end: 'first' }, { name: 'b', piece: 1, end: 'last' }],
  jun: [{ name: 'node', piece: 0, end: 'center' }],
  wir: [{ name: 'a', piece: 0, end: 'first' }, { name: 'b', piece: 0, end: 'last' }],
};

// ---- ids ----

let counter = 0;
/**
 * A short random token. Uses `crypto.getRandomValues` when it exists, which Safari also offers outside secure
 * contexts (unlike `crypto.randomUUID`), and `Math.random` otherwise. A counter keeps tokens distinct even then.
 */
export function defaultId(): string {
  const bytes = new Uint8Array(8);
  let filled = false;
  try {
    const c = (globalThis as { crypto?: { getRandomValues?: (a: Uint8Array) => unknown } }).crypto;
    if (c && typeof c.getRandomValues === 'function') {
      c.getRandomValues(bytes);
      filled = true;
    }
  } catch { /* fall back below */ }
  if (!filled) for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
  counter = (counter + 1) % 46656;
  return Array.from(bytes, (b) => (b % 36).toString(36)).join('') + counter.toString(36);
}

function token(factory?: IdFactory): string {
  let raw = '';
  try { raw = factory ? String(factory()) : ''; } catch { raw = ''; }
  return raw.replace(/[^A-Za-z0-9_]/g, '').slice(0, 40) || defaultId();
}

const ID_PATTERN = /^(stp-[a-z]{3}-[A-Za-z0-9_]{1,40})-(\d{1,2})$/;

/** The shared prefix of a stamp stroke's id, or null for any other stroke (a pen stroke, say). */
export function stampPrefix(id: string): string | null {
  const m = ID_PATTERN.exec(typeof id === 'string' ? id : '');
  return m ? m[1] : null;
}

/** Stroke ids grouped by stamp, in the order given. Ids that are not from a stamp are left out. */
export function groupByStamp(items: ReadonlyArray<string | { id: string }>): Map<string, string[]> {
  const groups = new Map<string, string[]>();
  for (const item of items) {
    const id = typeof item === 'string' ? item : item?.id;
    const prefix = stampPrefix(id);
    if (prefix) groups.set(prefix, [...(groups.get(prefix) ?? []), id]);
  }
  return groups;
}

/**
 * The ids to put in a `remove_strokes` note to undo the last thing drawn: every stroke of the last stroke's stamp,
 * or just that one stroke if it is not part of a stamp. Empty when there are no strokes.
 */
export function undoIds(strokes: readonly { id: string }[]): string[] {
  const last = strokes[strokes.length - 1];
  if (!last) return [];
  const prefix = stampPrefix(last.id);
  return prefix ? strokes.filter((s) => stampPrefix(s.id) === prefix).map((s) => s.id) : [last.id];
}

// ---- small helpers ----

const round2 = (v: number) => Math.round(v * 100) / 100 + 0; // + 0 turns -0 into 0
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

function quarterTurns(rotation: unknown): number {
  if (!finite(rotation)) return 0;
  return ((Math.round(rotation / 90) % 4) + 4) % 4;
}
function turn(k: number, x: number, y: number): Pt {
  return k === 0 ? [x, y] : k === 1 ? [-y, x] : k === 2 ? [-x, -y] : [y, -x];
}
function cleanLabel(label: unknown): string {
  if (label === undefined || label === null) return '';
  return Array.from(String(label).replace(/\s+/g, ' ').trim()).slice(0, MAX_VISIBLE_LABEL).join('');
}
// The server counts characters, the generated zod schema counts UTF-16 units. Staying under both keeps a stroke
// from being dropped when the board is rebuilt from saved events.
function describe(name: string, label: string, role?: string): string {
  let text = '';
  for (const ch of [name, label].filter(Boolean).join(' ') + (role ? ` [${role}]` : '')) {
    if (text.length + ch.length > MAX_STROKE_LABEL) break;
    text += ch;
  }
  return text;
}
function boardPoint(x: number, y: number): { x: number; y: number; pressure: number } {
  return { x: clamp(round2(x), 0, BOARD_WIDTH), y: clamp(round2(y), 0, BOARD_HEIGHT), pressure: PRESSURE };
}
function cleanPoint(p: unknown): { x: number; y: number; pressure: number } {
  const q = (p ?? {}) as Partial<PointLike>;
  const pressure = finite(q.pressure) ? clamp(q.pressure, 0, 1) : PRESSURE;
  return { ...boardPoint(finite(q.x) ? q.x : 0, finite(q.y) ? q.y : 0), pressure };
}

// ---- symbol geometry (scale 1, rotation 0, origin = the middle of the symbol, terminals 45 px either side) ----

function ring(r: number): Pt[] {
  return Array.from({ length: 9 }, (_, i) => [round2(r * Math.cos((i * Math.PI) / 4)), round2(r * Math.sin((i * Math.PI) / 4))] as Pt);
}

const DIODE: Piece[] = [
  { kind: 'path', role: 'anode side', pts: [[-45, 0], [-15, 0], [-15, -15], [15, 0], [-15, 15], [-15, -15]] },
  { kind: 'path', role: 'cathode side', pts: [[15, -15], [15, 15], [15, 0], [45, 0]] },
];
const LED_ARROWS: Piece[] = [
  { kind: 'arrow', role: 'light out', pts: [[-2, -18], [12, -32]] },
  { kind: 'arrow', role: 'light out', pts: [[8, -14], [22, -28]] },
];

function specFor(kind: SymbolKind, closed: boolean): Spec | null {
  switch (kind) {
    case 'resistor':
      return { name: 'resistor', notes: [], pieces: [{ kind: 'path', pts: [[-45, 0], [-27, 0], [-22.5, -9], [-13.5, 9], [-4.5, -9], [4.5, 9], [13.5, -9], [22.5, 9], [27, 0], [45, 0]] }] };
    case 'capacitor':
      return { name: 'capacitor', notes: [], pieces: [
        { kind: 'path', pts: [[-45, 0], [-6, 0], [-6, -15], [-6, 15]] },
        { kind: 'path', pts: [[45, 0], [6, 0], [6, -15], [6, 15]] }] };
    case 'led':
      return { name: 'LED', notes: [], pieces: [...DIODE, ...LED_ARROWS] };
    case 'diode':
      return { name: 'diode', notes: [], pieces: DIODE };
    case 'supply':
      return { name: 'DC supply', notes: [{ at: [20, -10], text: '+' }], pieces: [
        { kind: 'path', role: 'negative plate', pts: [[-45, 0], [-6, 0], [-6, -9], [-6, 9]] },
        { kind: 'path', role: 'positive plate', pts: [[45, 0], [6, 0], [6, -18], [6, 18]] }] };
    case 'ground':
      return { name: 'ground', notes: [], pieces: [
        { kind: 'path', pts: [[0, -24], [0, -6], [-18, -6], [18, -6]] },
        { kind: 'path', pts: [[-12, 3], [12, 3]] },
        { kind: 'path', pts: [[-6, 12], [6, 12]] }] };
    case 'switch':
      return { name: closed ? 'switch (closed)' : 'switch (open)', notes: [], pieces: [
        { kind: 'path', pts: closed ? [[-45, 0], [-21, 0], [21, 0]] : [[-45, 0], [-21, 0], [18, -21]] },
        { kind: 'path', pts: [[21, 0], [45, 0]] }] };
    case 'junction':
      return { name: 'junction', notes: [], pieces: [{ kind: 'path', pts: [...ring(3.5), [1.5, 0], ...ring(1.5).slice(1)] }] };
    default:
      return null;
  }
}

// ---- placing ----

type Box = { minx: number; maxx: number; miny: number; maxy: number };
function boxOf(points: readonly Pt[]): Box {
  const xs = points.map((p) => p[0]), ys = points.map((p) => p[1]);
  return { minx: Math.min(...xs), maxx: Math.max(...xs), miny: Math.min(...ys), maxy: Math.max(...ys) };
}
function union(a: Box, b: Box): Box {
  return { minx: Math.min(a.minx, b.minx), maxx: Math.max(a.maxx, b.maxx), miny: Math.min(a.miny, b.miny), maxy: Math.max(a.maxy, b.maxy) };
}

/** Pick the anchor coordinate: as close to `request` as the board allows; on the grid if asked and possible. */
function anchor(request: number, lo: number, hi: number, gridOffset: number | null): number {
  const v = clamp(request, lo, hi);
  if (gridOffset === null) return v;
  const k = Math.round((v - gridOffset) / GRID);
  const options = [k, k - 1, k + 1].map((n) => n * GRID + gridOffset).filter((c) => c >= lo - 1e-9 && c <= hi + 1e-9);
  return options.length ? options.reduce((best, c) => (Math.abs(c - v) < Math.abs(best - v) ? c : best)) : v;
}

function terminalsOf(prefix: string, members: Map<number, Stroke>): Terminal[] {
  const out: Terminal[] = [];
  for (const ref of TERMINAL_REFS[prefix.slice(4, 7)] ?? []) {
    const points = members.get(ref.piece)?.points;
    if (!points?.length) continue;
    if (ref.end === 'center') {
      const b = boxOf(points.map((p) => [p.x, p.y] as Pt));
      out.push({ name: ref.name, x: round2((b.minx + b.maxx) / 2), y: round2((b.miny + b.maxy) / 2), stamp: prefix });
    } else {
      const p = ref.end === 'first' ? points[0] : points[points.length - 1];
      out.push({ name: ref.name, x: p.x, y: p.y, stamp: prefix });
    }
  }
  return out;
}

/** The terminals of every stamp found in a stroke list, for example what the board has saved. */
export function terminalsFromStrokes(strokes: readonly Stroke[]): Terminal[] {
  const groups = new Map<string, Map<number, Stroke>>();
  for (const s of strokes) {
    const m = ID_PATTERN.exec(typeof s?.id === 'string' ? s.id : '');
    if (m && Array.isArray(s.points)) groups.set(m[1], (groups.get(m[1]) ?? new Map()).set(Number(m[2]), s));
  }
  return [...groups].flatMap(([prefix, members]) => terminalsOf(prefix, members));
}

function finish(kind: SymbolKind, prefix: string, strokes: Stroke[]): Placed {
  const members = new Map(strokes.map((s, i) => [i, s] as [number, Stroke]));
  return { kind, prefix, strokes, terminals: terminalsOf(prefix, members) };
}

function placeWire(from: unknown, o: StampOptions): Placed | null {
  const a = from as Partial<PointLike> | null | undefined, b = o.to as Partial<PointLike> | null | undefined;
  if (!a || !b || !finite(a.x) || !finite(a.y) || !finite(b.x) || !finite(b.y)) return null;
  const start = boardPoint(a.x, a.y), end = boardPoint(b.x, b.y);
  const pts = [start];
  const elbow = o.route === 'horizontal-first' ? { x: end.x, y: start.y } : o.route === 'vertical-first' ? { x: start.x, y: end.y } : null;
  if (elbow && start.x !== end.x && start.y !== end.y) pts.push(boardPoint(elbow.x, elbow.y)); // lined up: no corner needed
  pts.push(end);
  const prefix = `stp-wir-${token(o.ids)}`;
  return finish('wire', prefix, [{ id: `${prefix}-0`, kind: 'path', points: pts, label: describe('wire', cleanLabel(o.label)) }]);
}

/**
 * Stamp a symbol with its middle at `at` (a wire starts at `at` and ends at `options.to`).
 * Returns null when nothing can be drawn (see the notes at the top), otherwise the strokes and the terminal positions.
 */
export function placeStamp(kind: SymbolKind, at: PointLike, options: StampOptions = {}): Placed | null {
  const o = options ?? {};
  if (kind === 'wire') return placeWire(at, o);
  const spec = SYMBOL_KINDS.includes(kind) ? specFor(kind, o.closed === true) : null;
  if (!spec || !at || !finite(at.x) || !finite(at.y)) return null;

  const k = quarterTurns(o.rotation);
  const scale = finite(o.scale) && o.scale > 0 ? clamp(o.scale, MIN_SCALE, MAX_SCALE) : 1;
  const label = cleanLabel(o.label);
  const place = (p: Pt) => turn(k, p[0] * scale, p[1] * scale);
  const pieces = spec.pieces.map((p) => ({ ...p, pts: p.pts.map(place) }));
  const body = boxOf(pieces.flatMap((p) => p.pts));

  // Text strokes: the fixed notes, then the label beside the symbol (above a wide symbol, to the right of a tall one).
  const texts = spec.notes.map((n) => ({ at: place(n.at), text: n.text }));
  if (label) {
    const wide = body.maxx - body.minx >= body.maxy - body.miny;
    texts.push({ at: wide ? [body.minx, body.miny - 6] : [body.maxx + 8, (body.miny + body.maxy) / 2 + 4], text: label });
  }
  const total = texts.reduce((box, t) => union(box, {
    minx: t.at[0], maxx: t.at[0] + TEXT_WIDTH_PER_CHAR * Array.from(t.text).length, miny: t.at[1] - TEXT_ASCENT, maxy: t.at[1] + TEXT_DESCENT,
  }), body);

  const xLo = -total.minx, xHi = BOARD_WIDTH - total.maxx, yLo = -total.miny, yHi = BOARD_HEIGHT - total.maxy;
  if (xLo > xHi || yLo > yHi) return null; // cannot happen within the scale and label limits; kept as a safety net
  const first = TERMINAL_REFS[CODES[kind]][0];
  const firstPoint = pieces[first.piece].pts[0];
  const centre = first.end === 'center' ? ([0, 0] as Pt) : firstPoint;
  const mod = (v: number) => ((v % GRID) + GRID) % GRID;
  const ax = anchor(at.x, xLo, xHi, o.snapToGrid ? mod(-centre[0]) : null);
  const ay = anchor(at.y, yLo, yHi, o.snapToGrid ? mod(-centre[1]) : null);

  const prefix = `stp-${CODES[kind]}-${token(o.ids)}`;
  const strokes: Stroke[] = pieces.map((p, i) => ({
    id: `${prefix}-${i}`, kind: p.kind, points: p.pts.map(([x, y]) => boardPoint(ax + x, ay + y)), label: describe(spec.name, label, p.role),
  }));
  texts.forEach((t) => strokes.push({ id: `${prefix}-${strokes.length}`, kind: 'text', points: [boardPoint(ax + t.at[0], ay + t.at[1])], label: t.text }));
  return finish(kind, prefix, strokes);
}

/** The strokes of a stamp. An empty array means nothing could be drawn. */
export function stamp(kind: SymbolKind, at: PointLike, options: StampOptions = {}): Stroke[] {
  return placeStamp(kind, at, options)?.strokes ?? [];
}

/** A wire from one point to another, optionally with one right angle. Ends are clamped to the board, not shifted. */
export function wire(from: PointLike, to: PointLike, options: Omit<StampOptions, 'to'> = {}): Stroke[] {
  return stamp('wire', from, { ...options, to });
}

/** Where the terminals of a stamp would land, after any edge shift. Same as `placeStamp(...).terminals`. */
export function terminals(kind: SymbolKind, at: PointLike, options: StampOptions = {}): Terminal[] {
  return placeStamp(kind, at, options)?.terminals ?? [];
}

// ---- snapping ----

/** `p` moved onto the nearest multiple of `size` (default 30), kept on the board. A bad `p` becomes a valid point. */
export function gridSnap(p: PointLike, size: number = GRID): { x: number; y: number; pressure: number } {
  const q = cleanPoint(p), step = finite(size) && size > 0 ? size : GRID;
  return { ...boardPoint(Math.round(q.x / step) * step, Math.round(q.y / step) * step), pressure: q.pressure };
}

export type SnapTarget = Terminal | PointLike | Stroke;

function pointsOf(targets: readonly SnapTarget[]): Terminal[] {
  const strokes = targets.filter((t): t is Stroke => !!t && Array.isArray((t as Stroke).points));
  const plain = targets.filter((t): t is Terminal | PointLike => !!t && !Array.isArray((t as Stroke).points) && finite((t as PointLike).x) && finite((t as PointLike).y));
  return [...terminalsFromStrokes(strokes), ...plain.map((t) => ({ name: (t as Terminal).name ?? '', x: t.x, y: t.y, stamp: (t as Terminal).stamp ?? '' }))];
}

/** The terminal nearest to `p` within `radius` pixels (default 18), or null. Targets: terminals, points or strokes. */
export function nearestTerminal(p: PointLike, targets: readonly SnapTarget[], radius = 18): Terminal | null {
  const q = cleanPoint(p), r = finite(radius) && radius > 0 ? radius : 0;
  let best: Terminal | null = null, bestDistance = Infinity;
  for (const t of pointsOf(Array.isArray(targets) ? targets : [])) {
    const d = Math.hypot(t.x - q.x, t.y - q.y);
    if (d <= r && d < bestDistance) { best = t; bestDistance = d; }
  }
  return best;
}

/**
 * Where a pointer at `p` should land: exactly on the nearest terminal within `radius`, otherwise (if `grid` is set)
 * on the grid, otherwise where it was, kept on the board. Pressure is kept.
 */
export function snap(p: PointLike, targets: readonly SnapTarget[], radius = 18, options: { grid?: boolean | number } = {}) {
  const q = cleanPoint(p), hit = nearestTerminal(q, targets, radius);
  if (hit) return { ...boardPoint(hit.x, hit.y), pressure: q.pressure };
  const grid = options?.grid;
  return grid ? gridSnap(q, grid === true ? GRID : grid) : q;
}
