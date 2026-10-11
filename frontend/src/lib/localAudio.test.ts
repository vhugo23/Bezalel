import {it,expect} from 'vitest';
import {prepareSpeechAudio} from './localAudio';
it('bounds a synthesized startup spike and fades boundaries without changing the interior',()=>{
 const pcm=new Float32Array(2400).fill(.2);pcm[9]=-32;pcm[1000]=2;
 prepareSpeechAudio(pcm,24000);
 expect(pcm[0]).toBe(0);expect(pcm.at(-1)).toBe(0);
 expect(Math.abs(pcm[9])).toBeLessThan(.04);expect(pcm[1000]).toBe(1);
 expect(pcm[500]).toBeCloseTo(.2);
});
it('rejects nonfinite model output instead of playing it',()=>{
 expect(()=>prepareSpeechAudio(new Float32Array([NaN]),24000)).toThrow('Invalid');
});
