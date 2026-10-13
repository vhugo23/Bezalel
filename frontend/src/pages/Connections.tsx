import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';
import { Shell } from '../components/Shell';
import { Button, ErrorNotice, Badge } from '../components/ui';
import { connectionRequest, connectionSchema, readConnections, type Connections } from '../lib/connections';
import './Connections.css';

export function ConnectionsPage(){
 const query=useQuery({queryKey:['connections'],queryFn:readConnections,retry:false});
 const qc=useQueryClient();const [form,setForm]=useState<Connections>();
 const [keys,setKeys]=useState({llm_key:'',openai_speech_key:'',elevenlabs_key:''});
 const [busy,setBusy]=useState(false),[error,setError]=useState<unknown>(),[notice,setNotice]=useState('');
 const [device,setDevice]=useState('');
 useEffect(()=>{if(query.data)setForm(query.data);},[query.data]);
 const edit=<K extends keyof Connections>(key:K,value:Connections[K])=>setForm(old=>old?{...old,[key]:value}:old);
 async function save(){
  setBusy(true);setError(undefined);setNotice('');
  try{
   const updated=connectionSchema.parse(await connectionRequest('/providers',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...form,...keys})}));
   qc.setQueryData(['connections'],updated);setForm(updated);setKeys({llm_key:'',openai_speech_key:'',elevenlabs_key:''});
   await qc.invalidateQueries({queryKey:['voice-options']});setNotice('Connections saved. Restart voice in an open interview to use your new speech settings.');
  }catch(e){setError(e);}finally{setBusy(false);}
 }
 async function test(){
  setBusy(true);setError(undefined);setNotice('');
  try{await connectionRequest('/providers/test',{method:'POST'});setNotice('Your model connection works. You’re ready for a live interview.');}
  catch(e){setError(e);}finally{setBusy(false);}
 }
 async function checkDevice(){
  try{
   const adapter=await navigator.gpu?.requestAdapter();
   if(!adapter){setDevice('WebGPU is unavailable in this browser. Choose cloud speech, or try a supported browser with hardware acceleration.');return;}
   const gpu=await adapter.requestDevice();gpu.destroy();
   setDevice(adapter.features.has('shader-f16')?'WebGPU and compact Parakeet precision are available. First use still needs model downloads and enough GPU memory.':'WebGPU is available. Choose Parakeet compatibility mode or cloud speech; this GPU does not expose shader-f16.');
  }catch{setDevice('The browser could not start a GPU device. Choose cloud speech or check your graphics driver.');}
 }
 return <Shell crumb="Connections"><main className="page"><div className="wrap connections">
  <div className="connections-intro"><div><span className="eyebrow">Your providers. Your practice.</span><h1>Make Dana yours.</h1><p>Choose the model that interviews you, what listens, and how Dana sounds. Live speech stays interruptible—you can think aloud, ask questions, and cut in.</p></div><Badge tone={form?.ready?'ok':''}>{form?.ready?'Interviewer connected':'Connect an interviewer'}</Badge></div>
  <ErrorNotice error={error||query.error}/>{notice&&<p className="connection-notice" role="status">{notice}</p>}
  {form&&<form onSubmit={e=>{e.preventDefault();void save();}}>
   <section className="card connection-card"><div className="ch"><div><h2>01 · The interviewer</h2><p>Use a model with image input if you want whiteboard critique.</p></div></div><div className="cb connection-fields">
    <label>Provider<select aria-label="Provider" value={form.llm} onChange={e=>edit('llm',e.target.value as Connections['llm'])}><option value="none">Choose a provider</option><option value="gemini">Google Gemini</option><option value="openai">OpenAI</option><option value="anthropic">Anthropic Claude</option><option value="compatible">OpenAI-compatible / local model</option></select></label>
    <label>Model ID<input value={form.model} onChange={e=>edit('model',e.target.value)} placeholder="Model ID from your provider" autoComplete="off"/></label>
    {form.llm==='compatible'&&<label className="full">API base URL<input value={form.base_url} onChange={e=>edit('base_url',e.target.value)} placeholder="https://openrouter.ai/api/v1"/><small>OpenRouter, Groq, Mistral, DeepSeek, or a local endpoint. Self-hosted administrators can allow other provider hosts.</small></label>}
    <label className="full">API key<input type="password" value={keys.llm_key} onChange={e=>setKeys({...keys,llm_key:e.target.value})} placeholder={form.has_llm_key?'Saved securely · leave blank to keep it':'Paste your provider API key'} autoComplete="new-password" spellCheck={false}/></label>
    <details className="full"><summary>Separate model for grading and lessons</summary><label>Review model ID<input value={form.evaluator_model} onChange={e=>edit('evaluator_model',e.target.value)} placeholder="Leave blank to use the interviewer model"/></label></details>
   </div></section>
   <section className="card connection-card"><div className="ch"><div><h2>02 · What listens</h2><p>Your microphone stays active while Dana speaks. Headphones help prevent speaker echo.</p></div></div><div className="cb connection-fields">
    <label>Speech recognition<select aria-label="Speech recognition" value={form.stt} onChange={e=>edit('stt',e.target.value as Connections['stt'])}><option value="local">Parakeet · on this device</option><option value="elevenlabs">ElevenLabs · realtime captions</option><option value="openai">OpenAI · utterance transcription</option></select></label>
    {form.stt==='local'?<label>Parakeet precision<select aria-label="Parakeet precision" value={form.parakeet} onChange={e=>edit('parakeet',e.target.value as Connections['parakeet'])}><option value="quantized">Compact · FP16 encoder + INT8 decoder</option><option value="balanced">Compatibility · allows larger FP32 encoder</option></select></label>:form.stt==='openai'?<label>Transcription model<input value={form.stt_model} onChange={e=>edit('stt_model',e.target.value)}/></label>:<p className="fine">Streams partial and committed transcripts continuously through your ElevenLabs account.</p>}
    {form.stt==='local'&&<p className="fine full">Parakeet runs in your browser with a WebGPU encoder and quantized decoder. Compact mode downloads about 690 MB once; compatibility mode may need roughly 2.5 GB. Models stay cached when browser storage permits.</p>}
   </div></section>
   <section className="card connection-card"><div className="ch"><div><h2>03 · Dana’s voice</h2><p>Dana is an AI interviewer. Her voice is generated.</p></div></div><div className="cb connection-fields">
    <label>Voice engine<select aria-label="Voice engine" value={form.tts} onChange={e=>edit('tts',e.target.value as Connections['tts'])}><option value="local">Kokoro · on this device</option><option value="elevenlabs">ElevenLabs</option><option value="openai">OpenAI</option><option value="browser">Browser system voice</option></select></label>
    {form.tts==='local'&&<label>Kokoro voice<select aria-label="Kokoro voice" value={form.kokoro_voice} onChange={e=>edit('kokoro_voice',e.target.value as Connections['kokoro_voice'])}><option value="af_heart">Heart · warm</option><option value="af_bella">Bella</option><option value="af_nicole">Nicole</option><option value="af_sarah">Sarah</option></select></label>}
    {form.tts==='openai'&&<><label>Voice<input value={form.voice} onChange={e=>edit('voice',e.target.value)} placeholder="coral"/></label><label className="full">Speech model<input value={form.tts_model} onChange={e=>edit('tts_model',e.target.value)}/></label></>}
    {form.tts==='elevenlabs'&&<label>ElevenLabs voice ID<input value={form.elevenlabs_voice} onChange={e=>edit('elevenlabs_voice',e.target.value)} placeholder="Voice ID from your account"/></label>}
    {form.tts==='local'&&<p className="fine full">Kokoro downloads roughly 325 MB once and runs on WebGPU. The first start takes longer; subsequent interviews reuse cached model files.</p>}
   </div></section>
   {(form.stt==='openai'||form.tts==='openai')&&<section className="card connection-card cb"><label>OpenAI speech API key<input type="password" value={keys.openai_speech_key} onChange={e=>setKeys({...keys,openai_speech_key:e.target.value})} placeholder={form.has_openai_speech_key?'Saved · leave blank to keep it':form.llm==='openai'?'Leave blank to use your OpenAI model key':'Paste an OpenAI API key'} autoComplete="new-password"/></label></section>}
   {(form.stt==='elevenlabs'||form.tts==='elevenlabs')&&<section className="card connection-card cb"><label>ElevenLabs API key<input type="password" value={keys.elevenlabs_key} onChange={e=>setKeys({...keys,elevenlabs_key:e.target.value})} placeholder={form.has_elevenlabs_key?'Saved · leave blank to keep it':'Paste an ElevenLabs API key'} autoComplete="new-password"/></label></section>}
   <div className="connection-actions"><Button disabled={busy} type="submit">{busy?'Working…':'Save connections'}</Button><Button disabled={busy||!query.data?.ready} type="button" variant="outline" onClick={()=>void test()}>Test saved model</Button><Button type="button" variant="ghost" onClick={()=>void checkDevice()}>Check this device</Button></div>
   {device&&<p role="status" className="fine">{device}</p>}
   <p className="fine">PrepCrew adds no usage fee. Cloud requests are billed by your providers, including the one-request model test. A ChatGPT or Claude chat subscription is not an API key. Keys are encrypted by this app’s server and are never returned to your browser or included in practice exports.</p>
   <div className="connection-footer"><Link to="/plan">Return to practice</Link><Button disabled={busy} type="button" variant="ghost" onClick={async()=>{setBusy(true);try{await connectionRequest('/providers',{method:'DELETE'});await qc.invalidateQueries({queryKey:['connections']});setNotice('All saved provider keys removed.');}catch(e){setError(e);}finally{setBusy(false);}}}>Disconnect all providers</Button></div>
  </form>}
 </div></main></Shell>;
}
