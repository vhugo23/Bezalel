import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { expect, it } from 'vitest';

it('resamples 48 kHz mic input into bounded 16 kHz PCM frames without monitoring audio',()=>{
  const messages:{pcm:ArrayBuffer;level:number}[]=[];
  let Capture!:new()=>{process:(inputs:Float32Array[][])=>boolean};
  runInNewContext(readFileSync(new URL('../../public/audio/pcm-capture.js',import.meta.url),'utf8'),{
    AudioWorkletProcessor:class{port={postMessage:(data:{pcm:ArrayBuffer;level:number})=>messages.push(data)};},
    sampleRate:48000,Int16Array,Math,
    registerProcessor:(_name:string,constructor:typeof Capture)=>{Capture=constructor;},
  });
  const capture=new Capture();
  for(let i=0;i<75;i++)expect(capture.process([[new Float32Array(128).fill(.5)]])).toBe(true);
  expect(messages).toHaveLength(2);
  expect(messages[0].pcm.byteLength).toBe(3200);
  expect(messages[0].level).toBeCloseTo(.5);
  expect(new Int16Array(messages[0].pcm)[0]).toBe(16383);
});
