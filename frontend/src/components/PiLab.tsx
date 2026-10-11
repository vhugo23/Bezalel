import { useEffect, useRef, useState } from 'react';
import { z } from 'zod';
import { api, type Model } from '../api/client';
import { randomId } from '../lib/ids';
import { Badge, Button, ErrorNotice } from './ui';
import { PI_TRAY, Pi3D, webglAvailable, type PiPartId, type PiViewerHandle } from './Pi3D';

const labSchema=z.object({revision:z.number().int(),config:z.string(),file_path:z.string(),goal_ready:z.boolean(),
 label:z.string(),supply:z.string(),temperature_c:z.number(),
 browser:z.object({status:z.number(),css_status:z.number(),form_status:z.number(),latency_ms:z.number()})});
export function labReady(value:unknown){const parsed=labSchema.safeParse(value);return parsed.success&&parsed.data.goal_ready;}

export function PiLab({session,onChange}:{session:Model<'Session'>;onChange:()=>void|Promise<unknown>}){
 const result=labSchema.safeParse(session.engine_state?.lab);
 const lab=result.success?result.data:null;
 const [tab,setTab]=useState('Terminal'),[input,setInput]=useState(''),[draft,setDraft]=useState('');
 const [attached,setAttached]=useState<Record<'hat'|'camera',boolean>>({hat:false,camera:false}),[note,setNote]=useState<string|null>(null),[gl]=useState(webglAvailable),viewer=useRef<PiViewerHandle|null>(null);
 const [pending,setPending]=useState(false),[error,setError]=useState<unknown>(null);
 const retry=useRef<Model<'LabAction'>|null>(null),terminal=useRef<HTMLDivElement>(null);
 const actions=session.events.filter(e=>['command','edit','part_drop','probe'].includes(e.kind));
 useEffect(()=>{if(lab)setDraft(lab.config);},[lab?.config]);
 useEffect(()=>{terminal.current?.scrollTo({top:terminal.current.scrollHeight});},[actions.length,tab]);
 if(!lab)return <ErrorNotice error="The saved lab state could not be loaded. Refresh the session."/>;
 const disabled=pending||session.paused||session.status!=='live';
 const send=async(kind:Model<'LabAction'>['kind'],text:string,again=false)=>{
  if(disabled)return;
  const body=again&&retry.current?retry.current:{request_id:randomId(),revision:lab.revision,step:session.step,kind,text};
  retry.current=body;setPending(true);setError(null);
  try{await api.lab(session.id,body);retry.current=null;setInput('');await onChange();}
  catch(e){setError(e);await onChange();}finally{setPending(false);}
 };
 return <div className="pi-lab" data-revision={lab.revision}>
  <div className="lab-tabs" role="tablist" aria-label="Pi lab tools">{['Terminal','Editor','Browser','Pi'].map(name=><button key={name} role="tab" aria-selected={tab===name} onClick={()=>setTab(name)}>{name}</button>)}<Badge>Simulated</Badge></div>
  <p className="fine">{lab.label}. Explain your reasoning to Dana as you work.</p>
  <ErrorNotice error={error}/>{Boolean(error)&&retry.current&&<Button variant="outline" size="sm" disabled={disabled} onClick={()=>void send(retry.current!.kind,retry.current!.text,true)}>Retry saved action</Button>}
  {tab==='Terminal'&&<div className="lab-terminal">
   <div className="terminal-heading"><i/><i/><i/><span>pi@raspberrypi — bounded Linux lab</span></div>
   <div className="terminal-output" ref={terminal} role="log" aria-label="Terminal history">
    <p>Raspberry Pi 4 · synthetic filesystem and services<br/>Type help to see supported commands. Nothing runs on your computer.</p>
    {actions.map(e=><div className="terminal-entry" key={e.seq}><span className="terminal-command">{e.kind==='command'?'pi@raspberrypi:~ $ ':`${e.kind}: `}{String(e.payload.input)}</span><pre>{String(e.payload.output)}</pre><span className="terminal-seq">#{e.seq}</span></div>)}
   </div>
   <form onSubmit={e=>{e.preventDefault();if(input.trim())void send('command',input.trim());}}><label htmlFor="lab-command">$</label><input id="lab-command" aria-label="Terminal command" autoComplete="off" spellCheck={false} value={input} onChange={e=>setInput(e.target.value)} placeholder="help" disabled={disabled}/><button disabled={disabled||!input.trim()}>Run</button></form>
  </div>}
  {tab==='Editor'&&<div className="lab-editor"><div className="row"><code>{lab.file_path}</code><Button size="sm" disabled={disabled||draft===lab.config} onClick={()=>void send('edit',draft)}>Save config</Button></div><textarea aria-label="nginx configuration" spellCheck={false} value={draft} onChange={e=>setDraft(e.target.value)} disabled={disabled}/><p className="fine">Save, validate, reload, then verify. This simulator checks a restricted server-block grammar.</p></div>}
  {tab==='Browser'&&<div className="lab-browser"><div className="lab-address"><span>http://raspberrypi.local</span><Button size="sm" variant="outline" disabled={disabled} onClick={()=>void send('browser','refresh')}>Refresh site</Button></div>
   {lab.browser.status!==200?<div className="browser-error"><b>{lab.browser.status}</b><h2>Bad Gateway</h2><p>nginx · simulated response</p></div>:<div className={`lab-portfolio ${lab.browser.css_status===200?'styled':''}`}><header><b>Pi portfolio</b><span>Work · About · Contact</span></header><h2>Small things.<br/>Real engineering.</h2><p>A synthetic site served by a simulated Raspberry Pi.</p><div className="portfolio-projects"><article><b>Temperature logger</b><p>Embedded systems</p></article><article><b>Pi site</b><p>Linux & infrastructure</p></article></div><Button disabled={disabled} onClick={()=>void send('browser','contact')}>Test contact form</Button><p className="fine">Check the recorded response in Terminal.</p></div>}
   <div className="lab-browser-meta">Page HTTP {lab.browser.status} · CSS HTTP {lab.browser.css_status} · {lab.browser.latency_ms} ms simulated response</div>
  </div>}
  {tab==='Pi'&&<div className="lab-hardware"><div className="pi-layout"><div className="pi-scene" role="img" aria-label="Simulated Raspberry Pi 4 and USB-C power supply">{gl?<Pi3D handle={viewer} supply={lab.supply.startsWith('Unbranded')?'weak':'good'} disabled={disabled} onSupply={k=>void send('part',k==='good'?'good':'weak')} onAttach={(id,on)=>setAttached(a=>({...a,[id]:on}))} onNote={setNote}/>:<svg viewBox="0 0 500 300"><defs><linearGradient id="pcb" x2="1" y2="1"><stop stopColor="#3f9778"/><stop offset="1" stopColor="#1e6151"/></linearGradient></defs><ellipse cx="250" cy="245" rx="175" ry="20" fill="#d5d8df" opacity=".45"/><g transform="translate(110 58) skewY(-9)"><rect x="3" y="12" width="280" height="170" rx="15" fill="#174e41"/><rect width="280" height="170" rx="15" fill="url(#pcb)"/><rect x="105" y="53" width="65" height="65" rx="5" fill="#363b42" stroke="#a5b1b4" strokeWidth="5"/><rect x="228" y="20" width="65" height="58" rx="4" fill="#bdc5cb"/><rect x="228" y="93" width="65" height="58" rx="4" fill="#bdc5cb"/><rect x="27" y="-7" width="145" height="15" rx="3" fill="#272a30"/>{Array.from({length:16},(_,i)=><path key={i} d={`M${34+i*8} -5v10`} stroke="#dab85b" strokeWidth="3"/>)}<rect x="22" y="151" width="35" height="28" rx="4" fill="#c7cbd1"/><circle cx="18" cy="18" r="5" fill="#e2c77d"/><circle cx="262" cy="154" r="5" fill="#e2c77d"/><text x="19" y="133" fill="#e1f3e8" fontSize="13">Raspberry Pi 4 · simulation</text></g><path d="M150 225Q120 280 45 250" fill="none" stroke="#575c69" strokeWidth="9"/></svg>}</div><aside className="pi-tray" aria-label="Parts">
    <h3>Parts</h3>
    {PI_TRAY.map(t=>{const fitted=t.id==='supply'?!lab.supply.startsWith('Unbranded'):attached[t.id];
     return <div key={t.id} className={`pi-part ${fitted?'fitted':''}`}>
      <button className="pi-part-grab" disabled={disabled||fitted||!gl} onPointerDown={e=>{if(e.button!==0)return;e.preventDefault();viewer.current?.beginDrag(t.id,e);}} onClick={e=>{if(e.detail===0)viewer.current?.place(t.id);}}>
       <b>{t.name}</b><small>{fitted?`Fitted on ${t.target}`:`Drag onto the ${t.target}`}</small><small>{t.note}</small>
      </button>
      {fitted&&t.id!=='supply'&&<Button size="sm" variant="outline" disabled={disabled} onClick={()=>viewer.current?.remove(t.id)}>Remove</Button>}
     </div>;})}
    {note&&<p className="fine" role="status">{note}</p>}
    <p className="fine">{gl?'Drag a part onto the board, or click it. Hover any chip to see what it does.':'3D is unavailable in this browser; use the button below.'}</p>
   </aside></div><div className="lab-parts"><div><b>USB-C power</b><p>{lab.supply}</p><span className="fine">SoC: {lab.temperature_c} °C · synthetic reading</span></div><Button disabled={disabled} onClick={()=>void send('part',lab.supply.startsWith('Unbranded')?'good':'weak')}>{lab.supply.startsWith('Unbranded')?'Fit 5 V / 3 A supply + cable':'Fit original supply'}</Button></div><p className="fine">Power state changes the simulated workload. Inspect current and historical flags in Terminal.</p></div>}
  <div className={`lab-check ${lab.goal_ready?'ready':''}`} role="status">{lab.goal_ready?'Lab check complete. Explain the result to Dana, then continue.':'Investigate, make a scoped change, and verify your result.'}</div>
 </div>;
}
