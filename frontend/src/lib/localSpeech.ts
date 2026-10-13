import { z } from 'zod';
import { apiFetch, apiJson } from '../api/client';

const result=z.object({id:z.number(),ready:z.boolean().optional(),text:z.string().optional(),wav:z.instanceof(ArrayBuffer).optional(),error:z.string().optional()});
type Result=z.infer<typeof result>;
const jobSchema=z.object({id:z.string(),text:z.string()});
const progressSchema=z.object({type:z.literal('progress'),model:z.string(),stage:z.enum(['download','prepare']),loaded:z.number(),total:z.number(),cached:z.boolean()});
export type LoadProgress=Omit<z.infer<typeof progressSchema>,'type'>;
export class LocalSpeech {
  private worker:Worker;
  private serial=0;
  closed=false;
  loaded=false;
  private pending=new Map<number,{resolve:(r:Result)=>void;reject:(e:Error)=>void;timer:ReturnType<typeof setTimeout>}>();
  constructor(private kind:'stt'|'tts',public progress:(p:LoadProgress)=>void){
    this.worker=new Worker(new URL('./localSpeech.worker.ts',import.meta.url),{type:'module'});
    this.worker.onmessage=({data})=>{
      if(data?.type==='progress'){const p=progressSchema.safeParse(data);if(p.success){const {type:_,...rest}=p.data;this.progress(rest);}return;}
      const parsed=result.safeParse(data);if(!parsed.success){this.close();return;}
      const p=this.pending.get(parsed.data.id);if(!p)return;
      clearTimeout(p.timer);this.pending.delete(parsed.data.id);
      if(parsed.data.error)p.reject(new Error(parsed.data.error));else p.resolve(parsed.data);
    };
    this.worker.onerror=()=>this.close();
  }
  private call(data:Record<string,unknown>):Promise<Result>{
    if(this.closed)return Promise.reject(new Error('Local speech stopped.'));
    const id=++this.serial;
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{this.close();},data.load?900_000:120_000);
      this.pending.set(id,{resolve,reject,timer});
      try{this.worker.postMessage({id,kind:this.kind,...data});}
      catch{this.close();}
    });
  }
  async load(options?:{parakeet?:'balanced'|'quantized'}){
    try{await this.call({load:true,...options});this.loaded=true;}
    catch(e){this.close();throw e;}
  }
  async infer(sid:string,input:{text?:string;seq?:number;pcm?:Float32Array;voice?:string}){
    const path=`/sessions/${sid}/local-speech/jobs`;
    const started=await apiFetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:this.kind,seq:input.seq})});
    if(!started.ok)throw new Error('Could not audit local speech. Your conversation is saved.');
    const job=jobSchema.parse(await apiJson(started));
    let status='failed',text='';const began=performance.now();
    try{
      // TTS text comes from the saved interviewer event, never arbitrary client text.
      const output=await this.call({text:job.text,pcm:input.pcm,voice:input.voice});
      status='succeeded';text=output.text||'';return {...output,inference_id:job.id};
    }finally{
      const saved=await apiFetch(`${path}/${job.id}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status,text,latency_ms:Math.min(600000,Math.round(performance.now()-began))})});
      if(!saved.ok)throw new Error('Could not save the local speech audit. Please restart voice.');
    }
  }
  close(){
    this.closed=true;
    this.worker.terminate();
    for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(new Error('Local speech stopped. Continue by typing or restart voice.'));}
    this.pending.clear();
  }
}

// Model files live in Cache Storage; ask the browser not to evict them under pressure.
let persisted=false;
// Loaded models stay on the GPU between voice starts. Idle workers are freed after a while.
const IDLE_MS=15*60_000;
const shared:Partial<Record<'stt'|'tts',{speech:LocalSpeech;mode:string;idle?:ReturnType<typeof setTimeout>}>>={};
export function acquireSpeech(kind:'stt'|'tts',progress:(p:LoadProgress)=>void,mode='balanced'){
  if(!persisted){persisted=true;void navigator.storage?.persist?.().catch(()=>false);}
  let entry=shared[kind];
  if(entry&&entry.mode!==mode){clearTimeout(entry.idle);entry.speech.close();entry=undefined;}
  if(!entry||entry.speech.closed)entry=shared[kind]={speech:new LocalSpeech(kind,progress),mode};
  clearTimeout(entry.idle);entry.idle=undefined;entry.speech.progress=progress;
  return entry.speech;
}
export function releaseSpeech(speech:LocalSpeech|null){
  const entry=Object.values(shared).find(e=>e?.speech===speech);
  if(!entry){speech?.close();return;}
  entry.speech.progress=()=>{};clearTimeout(entry.idle);
  // Cancelling a first download must release the network and GPU immediately.
  if(!entry.speech.loaded){entry.speech.close();return;}
  entry.idle=setTimeout(()=>entry.speech.close(),IDLE_MS);
}
