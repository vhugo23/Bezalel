import { describe, expect, it } from 'vitest';
import { schemas } from '../api/schemas';
import sample from '../../../contracts/examples/circuit_stamps.sample.json';
import { sampleCircuit } from './circuitSymbols.sample';
import { SYMBOL_KINDS, groupByStamp, stampPrefix, terminalsFromStrokes } from './circuitSymbols';

describe('the committed sample strokes (contracts/examples/circuit_stamps.sample.json)', () => {
  it('are exactly what the library makes now; if this fails run `node scripts/circuit-stamps-sample.mjs` in frontend/', () => {
    expect(sample.strokes).toEqual(sampleCircuit());
  });
  it('cover every kind of symbol, parse with the generated zod schema, and have terminals that can be found again', () => {
    const codes = new Set(sample.strokes.map((s) => /^stp-([a-z]{3})-/.exec(s.id)?.[1]));
    expect([...codes].sort()).toEqual(['cap', 'dio', 'gnd', 'jun', 'led', 'res', 'sup', 'swi', 'wir']);
    expect(SYMBOL_KINDS).toHaveLength(codes.size);
    for (const s of sample.strokes) expect(schemas.Stroke.safeParse(s).success, s.id).toBe(true);
    expect(groupByStamp(sample.strokes).size).toBe(new Set(sample.strokes.map((s) => stampPrefix(s.id))).size);
    expect(terminalsFromStrokes(sample.strokes as never).length).toBeGreaterThan(15);
  });
});
