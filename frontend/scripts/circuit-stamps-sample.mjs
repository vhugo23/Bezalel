// Writes contracts/examples/circuit_stamps.sample.json from src/lib/circuitSymbols.sample.ts.
// Run from frontend/ (Node 22.18 or newer, which runs the TypeScript directly):  node scripts/circuit-stamps-sample.mjs
// src/lib/circuitSymbols.sample.test.ts fails when the committed file differs from what this would write.
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { sampleCircuit } from '../src/lib/circuitSymbols.sample.ts';

const out = fileURLToPath(new URL('../../contracts/examples/circuit_stamps.sample.json', import.meta.url));
const header = [
  '  "synthetic": true,',
  '  "note": "Strokes made by frontend/src/lib/circuitSymbols.ts, a drawing aid only. backend/tests/test_circuit_stamps_contract.py checks every one against app.v2.models.Stroke.",',
  '  "regenerate": "cd frontend && node scripts/circuit-stamps-sample.mjs",',
];
const strokes = sampleCircuit().map((s) => '    ' + JSON.stringify(s));
writeFileSync(out, ['{', ...header, '  "strokes": [', strokes.join(',\n'), '  ]', '}', ''].join('\n'));
console.log(`wrote ${strokes.length} strokes to ${out}`);
