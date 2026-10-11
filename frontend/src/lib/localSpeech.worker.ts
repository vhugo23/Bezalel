/// <reference lib="webworker" />
/// <reference types="@webgpu/types" />
import { KokoroTTS, env as kokoroEnv } from 'kokoro-js';
import { StyleTextToSpeech2Model, AutoTokenizer, type PretrainedModelOptions } from '@huggingface/transformers';
import { fromUrls, type ParakeetModel } from 'parakeet.js';
import { prepareSpeechAudio } from './localAudio';

// Transformers 3's bundled WASM assets predate ORT 1.30's asyncify module.
// Keep JavaScript and WASM on the same pinned runtime version.
kokoroEnv.wasmPaths='https://cdn.jsdelivr.net/npm/onnxruntime-web@1.30.0/dist/';

let tts:Promise<KokoroTTS>|undefined,stt:Promise<ParakeetModel>|undefined;
// Files download in parallel, so report one byte total per model instead of
// alternating per-file percentages. Floors keep early small files from reading as 100%.
type Model='Kokoro'|'Parakeet';
const downloads:Record<Model,{floor:number;cached:boolean;sent:string;files:Map<string,{loaded:number;total:number;done:boolean}>}>={
  Kokoro:{floor:325534210,cached:true,sent:'',files:new Map()},Parakeet:{floor:689995744,cached:true,sent:'',files:new Map()},
};
function report(model:Model){
  const d=downloads[model];let loaded=0,total=0,open=0;
  for(const f of d.files.values()){loaded+=f.loaded;total+=Math.max(f.total,f.loaded);if(!f.done)open++;}
  total=Math.max(total,d.floor);
  // After the bytes land, ONNX session setup on the GPU can take a while.
  const stage=!open&&loaded>=d.floor?'prepare':'download',key=`${stage}:${Math.floor(100*loaded/total)}`;
  if(key===d.sent)return;d.sent=key;
  self.postMessage({type:'progress',model,stage,loaded,total,cached:d.cached&&d.files.size>0});
}
function fileProgress(model:Model,file:string,update:{loaded?:number;total?:number;done?:boolean}){
  const files=downloads[model].files;files.set(file,{...(files.get(file)??{loaded:0,total:0,done:false}),...update});report(model);
}
const parakeetBase='https://huggingface.co/ysdede/parakeet-tdt-0.6b-v3-onnx/resolve/f88260fa0777fe0868dda6df85d1a98f012a4a7a/';
const quantizedBase='https://huggingface.co/hellguz/parakeet-tdt-0.6b-v3-onnx-q8/resolve/846e146169fdf7a3cfe9564bb3a3462373215dc9/';
let tracking=false;
function trackParakeetDownloads(){
  if(tracking)return;tracking=true;
  const original=globalThis.fetch.bind(globalThis);
  globalThis.fetch=async(input,init)=>{
    const url=typeof input==='string'?input:input instanceof URL?input.href:input.url;
    if(!url.startsWith(parakeetBase)&&!url.startsWith(quantizedBase))return original(input,init);
    fileProgress('Parakeet',url,{});
    const cache=await caches.open('prepcrew-local-speech-v1').catch(()=>null);
    const cached=await cache?.match(url).catch(()=>undefined);let response=cached;
    if(!response){
      downloads.Parakeet.cached=false;
      response=await original(input,init);
      if(response.ok)void cache?.put(url,response.clone()).catch(()=>{});
    }
    if(!response.ok||!response.body){fileProgress('Parakeet',url,{done:true});return response;}
    const total=Number(response.headers.get('content-length'))||0,reader=response.body.getReader();let loaded=0;
    fileProgress('Parakeet',url,{total});
    const body=new ReadableStream<Uint8Array>({
      async pull(controller){const chunk=await reader.read();if(chunk.done){fileProgress('Parakeet',url,{done:true});controller.close();return;}
        loaded+=chunk.value.length;fileProgress('Parakeet',url,{loaded});controller.enqueue(chunk.value);},
      cancel(reason){return reader.cancel(reason);},
    });
    return new Response(body,{status:response.status,statusText:response.statusText,headers:response.headers});
  };
}
async function gpu(){
  const adapter=await navigator.gpu?.requestAdapter();
  if(!adapter)throw new Error('WebGPU unavailable');
  // Fail before large downloads if the driver cannot create a GPU device.
  const device=await adapter.requestDevice();device.destroy();
  return adapter;
}
async function load(kind:'stt'|'tts'){
  if(kind==='tts'&&tts)return tts;
  if(kind==='stt'&&stt)return stt;
  const adapter=await gpu();
  if(kind==='tts'){
    report('Kokoro');
    // Replace the original vocoder's broken WebGPU ConvTranspose graph.
    const id='DevAmarnadhCG/Kokoro-82M-v1.0-ONNX-webgpu',revision='7d1a298d7e12fbfdd1e24a1d35f6c5181a0ad41a';
    const progress_callback:NonNullable<PretrainedModelOptions['progress_callback']>=p=>{
        if(p.status==='initiate')fileProgress('Kokoro',p.file,{});
        // transformers.js only emits 'download' on a cache miss.
        else if(p.status==='download')downloads.Kokoro.cached=false;
        else if(p.status==='progress')fileProgress('Kokoro',p.file,{loaded:p.loaded,total:p.total});
        else if(p.status==='done')fileProgress('Kokoro',p.file,{done:true});
    };
    return tts??=Promise.all([
      StyleTextToSpeech2Model.from_pretrained(id,{revision,device:'webgpu',dtype:'fp32',progress_callback}),
      AutoTokenizer.from_pretrained(id,{revision,progress_callback}),
    ]).then(([model,tokenizer])=>new KokoroTTS(model,tokenizer)).catch(e=>{tts=undefined;throw e;});
  }
  const fp16=adapter.features.has('shader-f16');
  downloads.Parakeet.floor=fp16?689995744:2495495162;
  trackParakeetDownloads();report('Parakeet');
  // Use explicit URLs: the hub helper materializes the large encoder as a Blob
  // URL, which failed to fetch in Chromium acceptance. Hybrid also explicitly
  // selects GPU encoder + WASM decoder and serializes ORT initialization.
  return stt??=fromUrls({
    encoderUrl:fp16?quantizedBase+'encoder-model.fp16.onnx':parakeetBase+'encoder-model.onnx',
    decoderUrl:parakeetBase+'decoder_joint-model.int8.onnx',tokenizerUrl:parakeetBase+'vocab.txt',
    ...(!fp16?{encoderDataUrl:parakeetBase+'encoder-model.onnx.data',filenames:{encoder:'encoder-model.onnx',decoder:'decoder_joint-model.int8.onnx'}}:{}),
    backend:'webgpu-hybrid',preprocessorBackend:'js',cpuThreads:1,
  }).catch(e=>{stt=undefined;throw e;});
}
// Serial execution within each dedicated worker prevents overlapping model calls.
let queue=Promise.resolve();
self.onmessage=({data}:{data:{id:number;kind:'stt'|'tts';load?:boolean;text?:string;pcm?:Float32Array}})=>{
  queue=queue.then(async()=>{
    try{
      const model=await load(data.kind);
      if(data.load){self.postMessage({id:data.id,ready:true});return;}
      if(data.kind==='tts'){
        const audio=await (model as KokoroTTS).generate(data.text!,{voice:'af_heart'});
        prepareSpeechAudio(audio.audio,audio.sampling_rate);
        const wav=audio.toWav();self.postMessage({id:data.id,wav},[wav]);
      }else{
        const result=await (model as ParakeetModel).transcribe(data.pcm!,16000,{enableProfiling:false});
        self.postMessage({id:data.id,text:result.utterance_text.slice(0,5000)});
      }
    }catch{
      self.postMessage({id:data.id,error:'Local speech could not run. Check WebGPU, available GPU memory and model download access. You can continue by typing.'});
    }
  });
};
