import { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react';
import { useParams } from 'react-router';
import { pairMessage, socketUrl, type Annotation, type Model, type Event } from '../api/client';
import { MAX_BATCH, activeItems, boardFromEvents, danaSkeletons, legacyToSkeletons, parseItem, validateMarks, type BoardItem } from '../lib/boardElements';
import { boardLoading } from '../components/Whiteboard';
import { randomId } from '../lib/ids';
import { Shell } from '../components/Shell';
import { Badge, ErrorNotice } from '../components/ui';

const BoardCanvas=lazy(()=>import('../components/BoardCanvas'));
type Pending={item:BoardItem;step:number};
const keyOf=(item:BoardItem)=>`${item.id}:${item.version}`;

export function PairPage(){
 const {code=''}=useParams();
 const ws=useRef<WebSocket|null>(null),inflight=useRef(new Map<string,string[]>());
 const [review,setReview]=useState<Model<'BoardResult'>|null>(null);
 const [events,setEvents]=useState<Event[]>([]),[pending,setPending]=useState<Pending[]>([]);
 const [status,setStatus]=useState('Connecting…'),[drawable,setDrawable]=useState(false),[step,setStep]=useState(0);
 const [error,setError]=useState<unknown>(null);
 const state=useRef({step,drawable,pending});state.current={step,drawable,pending};
 const key=`prepcrew-device:${code}`;
 const savePending=(items:Pending[])=>{setPending(items);state.current.pending=items;try{if(items.length)sessionStorage.setItem(`${key}:pending`,JSON.stringify(items));else sessionStorage.removeItem(`${key}:pending`);}catch{setError(new Error('Device recovery storage is full. Keep this tab open until your drawing is saved.'));}};
 const {latest,legacy}=useMemo(()=>boardFromEvents(events,step),[events,step]);
 const items=useMemo(()=>activeItems(latest),[latest]);
 const overlay=useMemo(()=>{if(!review)return [];try{return danaSkeletons(validateMarks(review.annotations as Annotation[],items));}catch{return [];}},[review,items]);
 // Send everything still unconfirmed for the current step. The server ignores a version it already has.
 const flush=()=>{
  const socket=ws.current;if(socket?.readyState!==WebSocket.OPEN||!state.current.drawable)return;
  const mine=state.current.pending.filter(p=>p.step===state.current.step).map(p=>p.item);
  for(let i=0;i<mine.length;i+=MAX_BATCH){
   const chunk=mine.slice(i,i+MAX_BATCH),batch=randomId(16);inflight.current.set(batch,chunk.map(keyOf));
   socket.send(JSON.stringify({type:'elements',step:state.current.step,batch,elements:chunk}));
  }
 };
 const save=(changed:BoardItem[])=>{
  const next=new Map(state.current.pending.map(p=>[p.item.id,p]));
  for(const item of changed)if((next.get(item.id)?.item.version??0)<item.version)next.set(item.id,{item,step:state.current.step});
  savePending([...next.values()]);flush();
 };
 useEffect(()=>{
  const settled=state.current.pending.filter(p=>(latest.get(p.item.id)?.version??0)<p.item.version);
  if(settled.length!==state.current.pending.length)savePending(settled);
 },[latest]);
 useEffect(()=>{
  let disposed=false,timer:ReturnType<typeof setTimeout>,attempt=0;
  let token=sessionStorage.getItem(key);
  if(!token){token=randomId(32);sessionStorage.setItem(key,token);}
  try{const stored:unknown=JSON.parse(sessionStorage.getItem(`${key}:pending`)||'[]');if(Array.isArray(stored))savePending(stored.slice(0,2000).flatMap(p=>{const item=parseItem(p?.item);return item&&Number.isInteger(p.step)?[{item,step:p.step as number}]:[];}));}catch{sessionStorage.removeItem(`${key}:pending`);}
  const connect=()=>{
   const socket=new WebSocket(socketUrl(`/ws/v2/pair/${encodeURIComponent(code)}`));ws.current=socket;
   socket.onopen=()=>socket.send(JSON.stringify({type:'hello',token}));
   socket.onmessage=ev=>{
    if(disposed)return;
    try{
     const m=pairMessage.parse(JSON.parse(ev.data));
     if(m.type==='paired'){attempt=0;setStatus('Connected · syncing board');setError(null);}
     else if(m.type==='state'){
      const changed=m.step!==state.current.step||m.drawable!==state.current.drawable;
      setStep(m.step);setDrawable(m.drawable);state.current.step=m.step;state.current.drawable=m.drawable;
      setStatus(m.drawable?'Connected · ready to draw':'Connected · waiting for whiteboard');
      if(changed||inflight.current.size===0)flush();
     }else if(m.type==='event'){
      const event=m.event as Event;
      setEvents(old=>[...old.filter(e=>e.seq!==event.seq),event].sort((a,b)=>a.seq-b.seq));
     }
     else if(m.type==='ack'){
      setError(null);const done=new Set(m.ids);if(m.batch)inflight.current.delete(m.batch);
      savePending(state.current.pending.filter(p=>!done.has(keyOf(p.item))));
     }
     else if(m.type==='review')setReview(m.review as Model<'BoardResult'>|null);
     else {
      setError(new Error(m.message));
      // A refused batch is not retried forever; a stale edit is settled when the newer saved version arrives.
      const refused=m.batch?new Set(inflight.current.get(m.batch)):null;
      if(m.batch)inflight.current.delete(m.batch);
      if(refused&&!/newer version|another step|paused/i.test(m.message))savePending(state.current.pending.filter(p=>!refused.has(keyOf(p.item))));
     }
    }catch{setError(new Error('Invalid pairing response'));}
   };
   socket.onclose=ev=>{if(disposed)return;inflight.current.clear();setDrawable(false);state.current.drawable=false;setStatus('Disconnected · reconnecting');if(ev.code===4404||ev.code===4400){setStatus('Pairing expired · request a new code');return;}timer=setTimeout(connect,Math.min(10000,500*2**attempt++));};
   socket.onerror=()=>setError(new Error('Connection interrupted. Your unsaved drawing stays on this device until reconnect.'));
  };
  connect();return()=>{disposed=true;clearTimeout(timer);ws.current?.close();};
 },[code]);
 return <Shell><main className="pair-page"><h1>Your whiteboard.</h1><p className="sub">Draw here. Talk to Dana on your laptop.</p>
  <Badge tone={drawable?'ok':'warn'}>{status}</Badge><ErrorNotice error={error}/>
  <div className="board-surface board-excalidraw paired-board"><Suspense fallback={boardLoading}><BoardCanvas key={step} label="Paired iPad whiteboard" saved={latest} extra={legacyToSkeletons(legacy)} overlay={overlay} readOnly={!drawable} onEdit={save} saveState={pending.some(p=>p.step===step)?'saving':'saved'}/></Suspense></div>
  <p className="fine">Apple Pencil, touch, or mouse · reconnect works in this tab for up to 24 hours.</p>
 </main></Shell>;
}
