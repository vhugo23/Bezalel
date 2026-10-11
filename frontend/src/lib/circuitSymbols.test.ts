import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Stroke } from '../api/client';
import { schemas } from '../api/schemas';
import { bounds, HEIGHT, WIDTH } from './board';
import {
  BOARD_HEIGHT, BOARD_WIDTH, GRID, SYMBOL_KINDS, defaultId, groupByStamp, gridSnap, nearestTerminal, placeStamp, snap, stamp,
  stampPrefix, terminals, terminalsFromStrokes, undoIds, wire, type StampOptions, type SymbolKind,
} from './circuitSymbols';

// The server's limits (backend/app/v2/models.py Point and Stroke) restated. Length is counted in UTF-16 units, as the
// generated zod schema does, which is the stricter of the two.
function problems(s: Stroke): string[] {
  const out: string[] = [];
  if (typeof s.id !== 'string' || s.id.length < 1 || s.id.length > 100) out.push('id');
  if (!['path', 'rect', 'arrow', 'text'].includes(s.kind)) out.push('kind');
  if (!Array.isArray(s.points) || s.points.length < 1 || s.points.length > 10000) out.push('point count');
  for (const p of s.points ?? []) {
    if (!Number.isFinite(p.x) || p.x < 0 || p.x > 900) out.push('x');
    if (!Number.isFinite(p.y) || p.y < 0 || p.y > 540) out.push('y');
    if (p.pressure !== undefined && !(p.pressure >= 0 && p.pressure <= 1)) out.push('pressure');
  }
  if (s.label !== undefined && (typeof s.label !== 'string' || s.label.length > 200)) out.push('label');
  return out;
}
function expectValid(strokes: Stroke[]) {
  const seen = new Set<string>();
  for (const s of strokes) {
    expect(problems(s), s.id).toEqual([]);
    expect(schemas.Stroke.safeParse(s).success, `zod: ${s.id}`).toBe(true);
    expect(() => bounds(s), `bounds: ${s.id}`).not.toThrow();
    expect(seen.has(s.id)).toBe(false);
    seen.add(s.id);
    expect(JSON.stringify(s)).not.toMatch(/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/); // no lone surrogate
  }
}
const ROTATIONS = [0, 90, 180, 270, -90, 450, 44, 46];
const SCALES = [0.5, 1, 1.5, 2, 3, 4];
const TWO_TERMINAL: SymbolKind[] = ['resistor', 'capacitor', 'led', 'diode', 'supply', 'switch'];
const SYMBOLS = SYMBOL_KINDS.filter((k) => k !== 'wire');
let counter = 0;
const ids = () => `t${counter++}`;
const rel = (strokes: Stroke[]) => { const o = strokes[0].points[0]; return strokes.map((s) => s.points.map((p) => [p.x - o.x, p.y - o.y])); };
const flat = (strokes: Stroke[]) => strokes.flatMap((s) => s.points);
afterEach(() => vi.unstubAllGlobals());

describe('constants', () => {
  it('match the board the renderer and the server use', () => {
    expect([BOARD_WIDTH, BOARD_HEIGHT]).toEqual([WIDTH, HEIGHT]);
    expect(GRID).toBe(30);
  });
});

describe('every symbol is valid against the server limits', () => {
  it.each(SYMBOLS)('%s at every rotation and several scales, with and without a label', (kind) => {
    for (const rotation of ROTATIONS) for (const scale of SCALES) for (const label of [undefined, 'R1 330Ω']) {
      const strokes = stamp(kind, { x: 450, y: 270 }, { rotation, scale, label, ids });
      expect(strokes.length).toBeGreaterThan(0);
      expectValid(strokes);
    }
  });

  it('draws what it says it draws, and says so in labels a model can read', () => {
    const r = stamp('resistor', { x: 450, y: 270 }, { label: 'R1 330Ω', ids });
    expect(r.map((s) => [s.kind, s.label])).toEqual([['path', 'resistor R1 330Ω'], ['text', 'R1 330Ω']]);
    expect(r[0].points).toHaveLength(10);
    const led = stamp('led', { x: 450, y: 270 }, { label: 'D1', ids });
    expect(led.map((s) => s.kind)).toEqual(['path', 'path', 'arrow', 'arrow', 'text']);
    expect(led.map((s) => s.label)).toEqual(['LED D1 [anode side]', 'LED D1 [cathode side]', 'LED D1 [light out]', 'LED D1 [light out]', 'D1']);
    expect(stamp('diode', { x: 450, y: 270 }, { ids }).map((s) => s.kind)).toEqual(['path', 'path']);
    expect(stamp('capacitor', { x: 450, y: 270 }, { ids })).toHaveLength(2);
    expect(stamp('ground', { x: 450, y: 270 }, { ids })).toHaveLength(3);
    const supply = stamp('supply', { x: 450, y: 270 }, { label: '5 V', ids });
    expect(supply.map((s) => s.label)).toEqual(['DC supply 5 V [negative plate]', 'DC supply 5 V [positive plate]', '+', '5 V']);
    expect(stamp('switch', { x: 450, y: 270 }, { ids })[0].label).toBe('switch (open)');
    expect(stamp('switch', { x: 450, y: 270 }, { closed: true, ids })[0].label).toBe('switch (closed)');
    expect(stamp('junction', { x: 450, y: 270 }, { ids })[0].label).toBe('junction');
  });

  it('a closed switch has a flat blade, an open one an angled blade', () => {
    const open = stamp('switch', { x: 450, y: 270 }, { ids })[0].points, closed = stamp('switch', { x: 450, y: 270 }, { closed: true, ids })[0].points;
    expect(new Set(closed.map((p) => p.y)).size).toBe(1);
    expect(open[open.length - 1].y).toBeLessThan(open[0].y);
  });

  it('keeps the label cut to 60 characters and the stroke label under 200', () => {
    const long = stamp('led', { x: 450, y: 270 }, { label: 'x'.repeat(10_000), ids });
    expectValid(long);
    expect(long[long.length - 1].label).toHaveLength(60);
    expect(Math.max(...long.map((s) => s.label!.length))).toBeLessThanOrEqual(200);
    const emoji = stamp('resistor', { x: 450, y: 270 }, { label: '😀'.repeat(500), ids });
    expectValid(emoji);
    expect(Array.from(emoji[1].label!)).toHaveLength(60);
    expect(stamp('resistor', { x: 450, y: 270 }, { label: ' \n\t R1 \r\n 10k ', ids })[1].label).toBe('R1 10k');
    expect(stamp('resistor', { x: 450, y: 270 }, { label: '   ', ids })).toHaveLength(1);
  });
});

describe('edges', () => {
  const spots = [[0, 0], [900, 0], [0, 540], [900, 540], [450, 0], [450, 540], [0, 270], [900, 270], [3, 5], [897, 537]];
  const opts: StampOptions[] = [{}, { label: 'a fairly long label R1 330Ω 1% metal film', scale: 2 }, { rotation: 90, scale: 4, label: 'D1' }, { rotation: 270, scale: 0.5 }];

  it.each(SYMBOLS)('%s stays inside the board at every corner and edge', (kind) => {
    for (const [x, y] of spots) for (const o of opts) {
      const strokes = stamp(kind, { x, y }, { ...o, ids });
      expect(strokes.length).toBeGreaterThan(0);
      expectValid(strokes);
    }
  });

  it.each(SYMBOLS)('%s is shifted whole, never deformed', (kind) => {
    for (const o of opts) {
      const centre = rel(stamp(kind, { x: 450, y: 270 }, { ...o, ids }));
      for (const [x, y] of spots) {
        const edge = rel(stamp(kind, { x, y }, { ...o, ids }));
        edge.forEach((points, i) => points.forEach(([dx, dy], j) => {
          expect(Math.abs(dx - centre[i][j][0])).toBeLessThanOrEqual(0.011);
          expect(Math.abs(dy - centre[i][j][1])).toBeLessThanOrEqual(0.011);
        }));
      }
    }
  });

  it('actually moves a symbol that would cross an edge, and not one that fits', () => {
    const fits = stamp('resistor', { x: 450, y: 270 }, { ids });
    expect(fits[0].points[0].x).toBe(405);
    const corner = stamp('resistor', { x: 0, y: 0 }, { ids });
    expect(Math.min(...flat(corner).map((p) => p.x))).toBe(0);
    expect(Math.max(...flat(stamp('resistor', { x: 900, y: 540 }, { ids })).map((p) => p.x))).toBe(900);
    expect(Math.min(...flat(stamp('led', { x: 450, y: 0 }, { ids })).map((p) => p.y))).toBe(0);
  });

  it('keeps a label on the board by shifting the symbol left, using an estimate of the text width', () => {
    const strokes = stamp('resistor', { x: 890, y: 270 }, { label: 'R1 a long label for the right edge', ids });
    const text = strokes[strokes.length - 1];
    expect(text.points[0].x + 7 * text.label!.length).toBeLessThanOrEqual(900.01);
  });
});

describe('odd input never throws', () => {
  it('returns [] when there is nothing to place', () => {
    for (const at of [{ x: NaN, y: 1 }, { x: 1, y: Infinity }, { x: -Infinity, y: 0 }, undefined, null, {}, { x: '5', y: 5 }] as never[]) {
      for (const kind of SYMBOLS) expect(stamp(kind, at, { ids })).toEqual([]);
    }
    expect(stamp('banana' as never, { x: 1, y: 1 })).toEqual([]);
    expect(stamp(undefined as never, { x: 1, y: 1 })).toEqual([]);
    expect(placeStamp('banana' as never, { x: 1, y: 1 })).toBeNull();
  });

  it('turns negative and huge positions into valid strokes at the nearest allowed place', () => {
    for (const at of [{ x: -50, y: -5 }, { x: 1e9, y: 1e9 }, { x: -1e308, y: 1e308 }, { x: Number.MAX_VALUE, y: -Number.MAX_VALUE }, { x: 0.1 + 0.2, y: 5e-324 }]) {
      for (const kind of SYMBOLS) expectValid(stamp(kind, at, { ids }));
    }
  });

  it('repairs bad options', () => {
    const bad: StampOptions[] = [
      { rotation: NaN }, { rotation: Infinity }, { rotation: -Infinity }, { rotation: 1e308 }, { rotation: '90' as never },
      { scale: NaN }, { scale: 0 }, { scale: -3 }, { scale: Infinity }, { scale: 1e9 }, { scale: 1e-9 }, { scale: '2' as never },
      { label: 5 as never }, { label: {} as never }, { label: null as never }, { ids: (() => { throw new Error('boom'); }) },
      { ids: (() => '') }, { ids: (() => '🙂 -- ') }, { ids: (() => 'a'.repeat(500)) }, { ids: (() => undefined as never) }, null as never,
    ];
    for (const o of bad) for (const kind of SYMBOLS) {
      const strokes = stamp(kind, { x: 450, y: 270 }, o);
      expect(strokes.length).toBeGreaterThan(0);
      expectValid(strokes);
    }
  });

  it('turns a bad scale into 1 and clamps a huge or tiny one', () => {
    const span = (scale: unknown) => { const [a, b] = terminals('resistor', { x: 450, y: 270 }, { scale: scale as number, ids }); return Math.hypot(b.x - a.x, b.y - a.y); };
    expect(span(NaN)).toBe(90);
    expect(span(-2)).toBe(90);
    expect(span(1e9)).toBe(360);
    expect(span(1e-9)).toBe(45);
  });

  it('rounds rotation to the nearest quarter turn', () => {
    const a = (rotation: number) => terminals('resistor', { x: 450, y: 270 }, { rotation, ids })[0];
    expect(a(44)).toEqual({ ...a(0), stamp: expect.any(String) });
    expect(a(46)).toEqual({ ...a(90), stamp: expect.any(String) });
    expect(a(-90)).toEqual({ ...a(270), stamp: expect.any(String) });
    expect(a(450)).toEqual({ ...a(90), stamp: expect.any(String) });
  });
});

describe('ids', () => {
  it('are unique across many stamps and carry a shared prefix per stamp', () => {
    const all: Stroke[] = [];
    for (let i = 0; i < 400; i++) all.push(...stamp(SYMBOLS[i % SYMBOLS.length], { x: 450, y: 270 }, { label: 'x' }));
    expect(new Set(all.map((s) => s.id)).size).toBe(all.length);
    const groups = groupByStamp(all);
    expect(groups.size).toBe(400);
    for (const [prefix, members] of groups) {
      expect(members.every((id) => id.startsWith(prefix + '-'))).toBe(true);
      expect(prefix).toMatch(/^stp-[a-z]{3}-[A-Za-z0-9_]+$/);
    }
    expect(Math.max(...all.map((s) => s.id.length))).toBeLessThan(40);
  });

  it('use one token per stamp from an injected function, cleaned up', () => {
    const calls: string[] = [];
    const factory = () => { calls.push('x'); return 'ab-cd ef:1234'; };
    const strokes = stamp('led', { x: 450, y: 270 }, { ids: factory, label: 'D1' });
    expect(calls).toHaveLength(1);
    expect(new Set(strokes.map((s) => stampPrefix(s.id))).size).toBe(1);
    expect(strokes[0].id).toBe('stp-led-abcdef1234-0');
    const uuid = '123e4567-e89b-12d3-a456-426614174000';
    expect(stamp('resistor', { x: 450, y: 270 }, { ids: () => uuid })[0].id).toBe('stp-res-123e4567e89b12d3a456426614174000-0');
    expect(stamp('resistor', { x: 450, y: 270 }, { ids: () => 'z'.repeat(300) })[0].id.length).toBeLessThanOrEqual(100);
  });

  it('are recognised only when they come from a stamp', () => {
    const [s] = stamp('resistor', { x: 450, y: 270 }, { ids: () => 'k1' });
    expect(stampPrefix(s.id)).toBe('stp-res-k1');
    for (const id of ['123e4567-e89b-12d3-a456-426614174000', 'limiter', 'redis', 'stp-res-k1', 'stp-RES-k1-0', '', 'stp-res--0']) expect(stampPrefix(id)).toBeNull();
    expect(stampPrefix(undefined as never)).toBeNull();
    expect([...groupByStamp(['limiter', 'stp-res-k1-0', 'stp-res-k1-1', 'stp-cap-k2-0'])]).toEqual([['stp-res-k1', ['stp-res-k1-0', 'stp-res-k1-1']], ['stp-cap-k2', ['stp-cap-k2-0']]]);
  });

  it('let a caller undo a whole stamp, or a single pen stroke', () => {
    const pen: Stroke = { id: '123e4567-e89b-12d3-a456-426614174000', kind: 'path', points: [{ x: 1, y: 1, pressure: 0.5 }], label: '' };
    const a = stamp('led', { x: 200, y: 200 }, { label: 'D1', ids: () => 'a1' }), b = stamp('resistor', { x: 600, y: 200 }, { label: 'R1', ids: () => 'b1' });
    expect(undoIds([pen, ...a, ...b])).toEqual(b.map((s) => s.id));
    expect(undoIds([...a, ...b, pen])).toEqual([pen.id]);
    expect(undoIds([pen, ...a])).toEqual(a.map((s) => s.id));
    expect(undoIds([])).toEqual([]);
    expect(undoIds([...b, pen, ...a]).length).toBe(a.length);
  });
});

describe('the id default', () => {
  const spyUuid = () => vi.fn(() => { throw new Error('randomUUID must not be called'); });
  it('works when crypto.randomUUID is undefined (Safari on plain http)', () => {
    vi.stubGlobal('crypto', { getRandomValues: (a: Uint8Array) => a.fill(7) });
    const strokes = stamp('resistor', { x: 450, y: 270 });
    expect(strokes[0].id).toMatch(/^stp-res-[a-z0-9]+-0$/);
    expectValid(strokes);
  });
  it('works when crypto is missing entirely', () => {
    vi.stubGlobal('crypto', undefined);
    const a = stamp('resistor', { x: 450, y: 270 }), b = stamp('resistor', { x: 450, y: 270 });
    expectValid(a);
    expect(a[0].id).not.toBe(b[0].id);
  });
  it('works when getRandomValues throws or is not a function', () => {
    vi.stubGlobal('crypto', { getRandomValues: () => { throw new Error('nope'); }, randomUUID: spyUuid() });
    expectValid(stamp('led', { x: 450, y: 270 }));
    vi.stubGlobal('crypto', { getRandomValues: 5 });
    expectValid(stamp('led', { x: 450, y: 270 }));
  });
  it('never calls randomUUID', () => {
    const randomUUID = spyUuid();
    vi.stubGlobal('crypto', { getRandomValues: (a: Uint8Array) => a.fill(1), randomUUID });
    for (const kind of SYMBOL_KINDS) stamp(kind, { x: 450, y: 270 }, { to: { x: 600, y: 270 } });
    expect(randomUUID).not.toHaveBeenCalled();
  });
  it('stays distinct even when the random source is constant', () => {
    vi.stubGlobal('crypto', { getRandomValues: (a: Uint8Array) => a.fill(0) });
    expect(new Set(Array.from({ length: 200 }, () => defaultId())).size).toBe(200);
  });
});

describe('terminals', () => {
  const at = { x: 450, y: 270 };
  const named = (kind: SymbolKind, o: StampOptions = {}) => Object.fromEntries(terminals(kind, at, { ids, ...o }).map((t) => [t.name, [t.x, t.y]]));

  it('sit where the symbol ends, at rotation 0 and turned clockwise', () => {
    expect(named('resistor')).toEqual({ a: [405, 270], b: [495, 270] });
    expect(named('resistor', { rotation: 90 })).toEqual({ a: [450, 225], b: [450, 315] });
    expect(named('resistor', { rotation: 180 })).toEqual({ a: [495, 270], b: [405, 270] });
    expect(named('resistor', { rotation: 270 })).toEqual({ a: [450, 315], b: [450, 225] });
    expect(named('led')).toEqual({ anode: [405, 270], cathode: [495, 270] });
    expect(named('led', { rotation: 180 })).toEqual({ anode: [495, 270], cathode: [405, 270] });
    expect(named('supply')).toEqual({ minus: [405, 270], plus: [495, 270] });
    expect(named('capacitor', { scale: 2 })).toEqual({ a: [360, 270], b: [540, 270] });
    expect(named('ground')).toEqual({ ground: [450, 246] });
    expect(named('junction')).toEqual({ node: [450, 270] });
    expect(Object.keys(named('diode'))).toEqual(['anode', 'cathode']);
    expect(Object.keys(named('switch'))).toEqual(['a', 'b']);
  });

  it.each(SYMBOLS)('of %s match the geometry that was drawn, after rotation, scaling and an edge shift', (kind) => {
    for (const rotation of [0, 90, 180, 270]) for (const scale of [0.5, 1, 2]) for (const where of [at, { x: 0, y: 0 }, { x: 900, y: 540 }]) {
      const placed = placeStamp(kind, where, { rotation, scale, label: 'X1', ids })!;
      expect(placed.terminals.length).toBeGreaterThan(0);
      // the same terminals come back from the strokes alone, also after a JSON round trip
      expect(terminalsFromStrokes(placed.strokes)).toEqual(placed.terminals);
      expect(terminalsFromStrokes(JSON.parse(JSON.stringify(placed.strokes)))).toEqual(placed.terminals);
      for (const t of placed.terminals) {
        expect(t.stamp).toBe(placed.prefix);
        if (kind === 'junction') continue;
        // a terminal is the end of one of the drawn lines
        expect(flat(placed.strokes.filter((s) => s.kind === 'path')).some((p) => p.x === t.x && p.y === t.y)).toBe(true);
      }
      if (TWO_TERMINAL.includes(kind)) {
        const [a, b] = placed.terminals;
        expect(Math.hypot(b.x - a.x, b.y - a.y)).toBeCloseTo(90 * scale, 1);
        expect([rotation % 180 === 0 ? a.y : a.x]).toEqual([rotation % 180 === 0 ? b.y : b.x]); // on one horizontal or vertical line
      }
    }
  });

  it('are found among other strokes and ignore pen strokes and broken stamps', () => {
    const pen: Stroke = { id: 'abc', kind: 'path', points: [{ x: 1, y: 1, pressure: 0.5 }], label: '' };
    const led = placeStamp('led', at, { ids: () => 'q1' })!, res = placeStamp('resistor', { x: 200, y: 100 }, { ids: () => 'q2' })!;
    const found = terminalsFromStrokes([pen, ...led.strokes, ...res.strokes]);
    expect(found).toEqual([...led.terminals, ...res.terminals]);
    expect(terminalsFromStrokes([pen, ...led.strokes.slice(1)]).map((t) => t.name)).toEqual(['cathode']); // the anode stroke is gone
    expect(terminalsFromStrokes([{ id: 'stp-res-q-0', kind: 'path', points: [] } as unknown as Stroke])).toEqual([]);
    expect(terminalsFromStrokes([null, undefined, {}] as never)).toEqual([]);
  });

  it('can be put on the 30 px grid', () => {
    for (const kind of SYMBOLS) for (const rotation of [0, 90, 180, 270]) for (const scale of [1, 2, 3, 4]) for (const where of [{ x: 451.4, y: 268.9 }, { x: 3, y: 4 }, { x: 898, y: 538 }, { x: 0, y: 270 }]) {
      const ts = terminals(kind, where, { rotation, scale, snapToGrid: true, ids });
      const strokes = stamp(kind, where, { rotation, scale, snapToGrid: true, ids });
      expectValid(strokes);
      for (const t of kind === 'junction' ? ts : ts.slice(0, TWO_TERMINAL.includes(kind) ? 2 : 1)) {
        expect(Math.abs(t.x / GRID - Math.round(t.x / GRID)), `${kind} ${rotation} ${scale} x=${t.x}`).toBeLessThan(0.001);
        expect(Math.abs(t.y / GRID - Math.round(t.y / GRID)), `${kind} ${rotation} ${scale} y=${t.y}`).toBeLessThan(0.001);
      }
    }
  });

  it('lands the first terminal on the grid for half scales too', () => {
    const [a] = terminals('resistor', { x: 451, y: 269 }, { scale: 0.5, snapToGrid: true, ids });
    expect(a.x % GRID).toBeCloseTo(0, 5);
    expect(a.y % GRID).toBeCloseTo(0, 5);
  });
});

describe('wires', () => {
  it('join two points, straight or with one right angle', () => {
    const p = (x: number, y: number) => ({ x, y });
    const pts = (s: Stroke[]) => s[0].points.map((q) => [q.x, q.y]);
    expect(pts(wire(p(100, 100), p(300, 200), { ids }))).toEqual([[100, 100], [300, 200]]);
    expect(pts(wire(p(100, 100), p(300, 200), { route: 'horizontal-first', ids }))).toEqual([[100, 100], [300, 100], [300, 200]]);
    expect(pts(wire(p(100, 100), p(300, 200), { route: 'vertical-first', ids }))).toEqual([[100, 100], [100, 200], [300, 200]]);
    expect(pts(wire(p(100, 100), p(300, 100), { route: 'vertical-first', ids }))).toEqual([[100, 100], [300, 100]]);
    expect(pts(wire(p(100, 100), p(100, 100), { route: 'horizontal-first', ids }))).toEqual([[100, 100], [100, 100]]);
    const w = wire(p(100, 100), p(300, 200), { label: 'VCC', ids });
    expect(w[0]).toMatchObject({ kind: 'path', label: 'wire VCC' });
    expectValid(w);
  });

  it('clamps its ends to the board and never throws', () => {
    const w = wire({ x: -20, y: -20 }, { x: 5000, y: 5000 }, { route: 'horizontal-first', ids });
    expectValid(w);
    expect(flat(w).every((q) => q.x >= 0 && q.x <= 900 && q.y >= 0 && q.y <= 540)).toBe(true);
    expect(wire({ x: 1, y: 1 }, undefined as never)).toEqual([]);
    expect(wire({ x: NaN, y: 1 }, { x: 1, y: 1 })).toEqual([]);
    expect(wire({ x: 1, y: 1 }, { x: 1, y: Infinity })).toEqual([]);
    expect(stamp('wire', { x: 1, y: 1 })).toEqual([]);
    expect(wire(null as never, null as never)).toEqual([]);
  });

  it('start and end exactly on snapped terminals', () => {
    const led = placeStamp('led', { x: 300, y: 200 }, { ids: () => 'l1' })!, res = placeStamp('resistor', { x: 600, y: 300 }, { ids: () => 'r1' })!;
    const board = [...led.strokes, ...res.strokes];
    const from = snap({ x: 349, y: 203 }, board), to = snap({ x: 557, y: 296, pressure: 0.9 }, board);
    const w = placeStamp('wire', from, { to, route: 'horizontal-first', ids: () => 'w1' })!;
    const cathode = led.terminals.find((t) => t.name === 'cathode')!, a = res.terminals.find((t) => t.name === 'a')!;
    expect([w.strokes[0].points[0].x, w.strokes[0].points[0].y]).toEqual([cathode.x, cathode.y]);
    const last = w.strokes[0].points[w.strokes[0].points.length - 1];
    expect([last.x, last.y]).toEqual([a.x, a.y]);
    expect(w.terminals.map((t) => [t.x, t.y])).toEqual([[cathode.x, cathode.y], [a.x, a.y]]);
    // a wire's own ends are terminals for the next wire
    expect(nearestTerminal({ x: cathode.x + 2, y: cathode.y }, [...board, ...w.strokes])).not.toBeNull();
  });
});

describe('snap', () => {
  const targets = [{ name: 'a', x: 100, y: 100, stamp: 's' }, { name: 'b', x: 110, y: 100, stamp: 's' }];
  it('goes to the nearest terminal within the radius, and only then', () => {
    expect(snap({ x: 108, y: 101 }, targets, 18)).toMatchObject({ x: 110, y: 100 });
    expect(snap({ x: 103, y: 101 }, targets, 18)).toMatchObject({ x: 100, y: 100 });
    expect(snap({ x: 150, y: 100 }, targets, 18)).toMatchObject({ x: 150, y: 100 });
    expect(snap({ x: 118, y: 100 }, targets, 8)).toMatchObject({ x: 110, y: 100 }); // exactly on the radius counts
    expect(snap({ x: 119, y: 100 }, targets, 8)).toMatchObject({ x: 119, y: 100 });
    expect(nearestTerminal({ x: 105, y: 100 }, targets)?.name).toBe('a'); // equal distance: the first one
  });
  it('keeps pressure and defaults the radius', () => {
    expect(snap({ x: 108, y: 100, pressure: 0.8 }, targets).pressure).toBe(0.8);
    expect(snap({ x: 108, y: 100 }, targets).pressure).toBe(0.5);
    expect(snap({ x: 108, y: 100, pressure: 7 }, targets).pressure).toBe(1);
    expect(snap({ x: 100 + 17, y: 100 }, [targets[0]])).toMatchObject({ x: 100 });
  });
  it('treats a zero, negative or bad radius as exact only', () => {
    for (const r of [0, -5, NaN, Infinity * -1]) {
      expect(snap({ x: 100.5, y: 100 }, targets, r)).toMatchObject({ x: 100.5 });
      expect(snap({ x: 100, y: 100 }, targets, r)).toMatchObject({ x: 100, y: 100 });
    }
  });
  it('takes points, terminals and strokes, and ignores junk', () => {
    const [led] = [placeStamp('led', { x: 300, y: 200 }, { ids: () => 'l1' })!];
    expect(snap({ x: 340, y: 202 }, led.strokes)).toMatchObject({ x: 345, y: 200 }); // the cathode of an LED stamped at 300,200
    expect(snap({ x: 300, y: 202 }, led.strokes)).toMatchObject({ x: 300, y: 202 }); // the middle of the symbol is not a terminal
    expect(snap({ x: 10, y: 10 }, [{ x: 12, y: 12 }])).toMatchObject({ x: 12, y: 12 });
    expect(snap({ x: 10, y: 10 }, [null, undefined, {}, { x: NaN, y: 1 }, 'x'] as never)).toMatchObject({ x: 10, y: 10 });
    expect(snap({ x: 10, y: 10 }, undefined as never)).toMatchObject({ x: 10, y: 10 });
    expect(snap({ x: 10, y: 10 }, [])).toMatchObject({ x: 10, y: 10 });
  });
  it('returns a valid point for any pointer input', () => {
    for (const p of [{ x: NaN, y: NaN }, { x: -5, y: 9999 }, { x: Infinity, y: -Infinity }, undefined, null, {}] as never[]) {
      const q = snap(p, targets);
      expect(Number.isFinite(q.x) && Number.isFinite(q.y)).toBe(true);
      expect(q.x >= 0 && q.x <= 900 && q.y >= 0 && q.y <= 540).toBe(true);
    }
  });
  it('can fall back to the 30 px grid', () => {
    expect(snap({ x: 133, y: 77 }, [], 18, { grid: true })).toMatchObject({ x: 120, y: 90 });
    expect(snap({ x: 133, y: 77 }, [], 18, { grid: 10 })).toMatchObject({ x: 130, y: 80 });
    expect(snap({ x: 105, y: 100 }, targets, 18, { grid: true })).toMatchObject({ x: 100, y: 100 }); // a terminal wins over the grid
    expect(gridSnap({ x: 14.9, y: 15 })).toMatchObject({ x: 0, y: 30 });
    expect(gridSnap({ x: 899, y: 539 })).toMatchObject({ x: 900, y: 540 });
    expect(gridSnap({ x: 5, y: 5 }, NaN)).toMatchObject({ x: 0, y: 0 });
    expect(gridSnap({ x: NaN, y: 1e9 })).toMatchObject({ x: 0, y: 540 });
  });
});

describe('the whole library against the server model', () => {
  it('every kind, option mix and place gives valid strokes', () => {
    for (const kind of SYMBOL_KINDS) for (const rotation of [0, 90, 180, 270]) for (const scale of [0.5, 1, 2, 4]) for (const where of [{ x: 0, y: 0 }, { x: 450, y: 270 }, { x: 900, y: 540 }]) {
      const placed = placeStamp(kind, where, { rotation, scale, label: 'R1 330Ω', snapToGrid: rotation === 90, closed: scale === 2, to: { x: 700, y: 400 }, route: 'vertical-first', ids });
      expect(placed).not.toBeNull();
      expectValid(placed!.strokes);
    }
  });
});
