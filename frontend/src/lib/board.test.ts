import { describe, it, expect } from 'vitest';
import { bounds, validateMarks } from './board';
import type { Annotation, Stroke } from '../api/client';
const stroke:Stroke={id:'redis',kind:'rect',points:[{x:460,y:340,pressure:.5},{x:630,y:404,pressure:.5}],label:'Redis'};
const mark:Annotation={id:'a',kind:'circle',severity:'probe',speech:'What fails?',target:'redis',geometry:{x:-9000},target_seq:1,event_seq:2};
describe('annotation geometry',()=>{
 it('ignores supplied coordinates and resolves the referenced stroke',()=>{expect(validateMarks([mark],[stroke])[0].geometry).toEqual(bounds(stroke));});
 it('rejects unknown, duplicate, oversized, and nonfinite input',()=>{
  expect(()=>validateMarks([mark],[])).toThrow();
  expect(()=>validateMarks([mark],[stroke,stroke])).toThrow();
  expect(()=>validateMarks(Array(5).fill(mark),[stroke])).toThrow();
  expect(()=>bounds({...stroke,points:[{x:NaN,y:4,pressure:.5}]})).toThrow();
 });
 it('clamps the annotation padding at canvas boundaries',()=>{expect(bounds({...stroke,points:[{x:0,y:0,pressure:.5},{x:900,y:540,pressure:.5}]})).toMatchObject({x:0,y:0,w:900,h:540});});
});
