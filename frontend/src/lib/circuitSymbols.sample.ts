// A fixed sample board made with circuitSymbols, for one purpose: the same strokes are committed as
// contracts/examples/circuit_stamps.sample.json, so the Python tests can check them against the server's Stroke model.
// Regenerate the file (from frontend/, Node 22.18 or newer):  node scripts/circuit-stamps-sample.mjs
// circuitSymbols.sample.test.ts fails when the committed file no longer matches this code.
import type { Stroke } from '../api/client';
import { placeStamp, stamp, wire, type StampOptions, type SymbolKind, type Terminal } from './circuitSymbols.ts';

export function sampleCircuit(): Stroke[] {
  let n = 0;
  const ids = () => `s${++n}`; // fixed tokens, so the output is the same every time
  const at = (kind: SymbolKind, x: number, y: number, o: StampOptions = {}) => placeStamp(kind, { x, y }, { ids, snapToGrid: true, ...o })!;
  const end = (t: Terminal[], name: string) => t.find((q) => q.name === name)!;

  // A supply, a resistor and an LED in a loop, joined by wires that start and end on terminals.
  const v1 = at('supply', 150, 270, { rotation: 270, label: 'V1 5 V' });
  const r1 = at('resistor', 330, 150, { label: 'R1 330Ω' });
  const d1 = at('led', 600, 270, { rotation: 90, label: 'D1' });
  const gnd = at('ground', 330, 420, { label: 'GND' });
  const parts = [v1, r1, d1, gnd];
  const join = (from: Terminal, to: Terminal, route: 'straight' | 'horizontal-first' | 'vertical-first') =>
    wire(from, to, { route, ids });
  const wires = [
    join(end(v1.terminals, 'plus'), end(r1.terminals, 'a'), 'vertical-first'),
    join(end(r1.terminals, 'b'), end(d1.terminals, 'anode'), 'horizontal-first'),
    join(end(d1.terminals, 'cathode'), end(gnd.terminals, 'ground'), 'vertical-first'),
    join(end(v1.terminals, 'minus'), end(gnd.terminals, 'ground'), 'vertical-first'),
  ];

  // One of everything else, and two that are pushed in from an edge.
  const extras = [
    stamp('capacitor', { x: 750, y: 90 }, { ids, label: 'C1 100nF' }),
    stamp('diode', { x: 750, y: 180 }, { ids, label: 'D2', rotation: 180 }),
    stamp('switch', { x: 750, y: 300 }, { ids, label: 'S1' }),
    stamp('switch', { x: 750, y: 380 }, { ids, closed: true, scale: 1.5 }),
    stamp('junction', { x: 450, y: 480 }, { ids }),
    stamp('resistor', { x: 0, y: 0 }, { ids, label: 'R2 a label long enough to push the symbol away from the left edge' }),
    stamp('led', { x: 900, y: 540 }, { ids, scale: 2, label: 'D3' }),
  ];
  return [...parts.flatMap((p) => p.strokes), ...wires.flat(), ...extras.flat()];
}
