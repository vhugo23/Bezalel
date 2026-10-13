import { z } from 'zod';
import { apiFetch, apiJson } from '../api/client';
export const speechOptions=z.object({stt:z.enum(['local','elevenlabs','openai']),tts:z.enum(['local','elevenlabs','openai','browser']),kokoro_voice:z.enum(['af_heart','af_bella','af_nicole','af_sarah']),parakeet:z.enum(['balanced','quantized']),ready:z.boolean()});
export type SpeechOptions=z.infer<typeof speechOptions>;
export const connectionSchema=speechOptions.extend({llm:z.enum(['none','gemini','openai','anthropic','compatible']),model:z.string(),evaluator_model:z.string(),base_url:z.string(),stt_model:z.string(),tts_model:z.string(),voice:z.string(),elevenlabs_voice:z.string(),has_llm_key:z.boolean(),has_openai_speech_key:z.boolean(),has_elevenlabs_key:z.boolean()});
export type Connections=z.infer<typeof connectionSchema>;
export async function connectionRequest(path:string,init?:RequestInit){
 const response=await apiFetch(path,init);const data=await apiJson(response);
 if(!response.ok){const detail=z.object({detail:z.unknown()}).safeParse(data);throw new Error(detail.success&&typeof detail.data.detail==='string'?detail.data.detail:'Could not update this connection. Check the selected model and settings.');}
 return data;
}
export async function readConnections(){return connectionSchema.parse(await connectionRequest('/providers'));}
export function wavPcm(samples:Float32Array):Blob{
 const buffer=new ArrayBuffer(44+samples.length*2),view=new DataView(buffer);
 const text=(offset:number,value:string)=>{for(let i=0;i<value.length;i++)view.setUint8(offset+i,value.charCodeAt(i));};
 text(0,'RIFF');view.setUint32(4,buffer.byteLength-8,true);text(8,'WAVE');text(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,16000,true);view.setUint32(28,32000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);text(36,'data');view.setUint32(40,samples.length*2,true);
 for(let i=0;i<samples.length;i++)view.setInt16(44+i*2,Math.max(-1,Math.min(1,samples[i]))*32767,true);
 return new Blob([buffer],{type:'audio/wav'});
}
