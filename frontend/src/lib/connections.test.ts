// @vitest-environment jsdom
import {it,expect} from 'vitest';
import {wavPcm,speechOptions} from './connections';
it('encodes bounded mono microphone samples as 16 kHz PCM16 WAV',async()=>{
 const blob=wavPcm(new Float32Array([-2,0,.5,2]));
 const bytes=await new Promise<ArrayBuffer>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result as ArrayBuffer);reader.onerror=reject;reader.readAsArrayBuffer(blob);});
 const view=new DataView(bytes);
 expect(String.fromCharCode(...new Uint8Array(bytes,0,4))).toBe('RIFF');
 expect(view.getUint32(24,true)).toBe(16000);expect(view.getUint16(22,true)).toBe(1);
 expect(view.getInt16(44,true)).toBe(-32767);expect(view.getInt16(50,true)).toBe(32767);
});
it('validates explicit local and cloud speech choices',()=>{
 expect(speechOptions.parse({stt:'openai',tts:'local',kokoro_voice:'af_sarah',parakeet:'quantized',ready:true}).tts).toBe('local');
 expect(speechOptions.safeParse({stt:'made-up'}).success).toBe(false);
});
