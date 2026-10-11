import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router';
import { pairMessage, socketUrl, type Annotation, type Model, type Event, type Stroke } from '../api/client';
import { drawStrokes, drawMarks, validateMarks, WIDTH, HEIGHT } from '../lib/board';
import { strokesFromEvents } from '../components/Whiteboard';
import { randomId } from '../lib/ids';
import { schemas } from '../api/schemas';
import { Shell } from '../components/Shell';
import { Badge, Button, ErrorNotice } from '../components/ui';

type Pending={stroke:Stroke;step:number};
export function PairPage(){
 const {code=''}=useParams();
 const canvas=useRef<HTMLCanvasElement>(null),overlay=useRef<HTMLCanvasElement>(null),ws=useRef<WebSocket|null>(null),draft=useRef<Stroke|null>(null);
 const [review,setReview]=useState<Model<'BoardResult'>|null>(null);
 const [events,setEvents]=useState<Event[]>([]),[pending,setPending]=useState<Pending[]>([]);
 const [status,setStatus]=useState('Connecting…'),[drawable,setDrawable]=useState(false),[step,setStep]=useState(0);
 const [tool,setTool]=useState<Stroke['kind']>('path'),[error,setError]=useState<unknown>(null);
 const state=useRef({step,drawable,pending});state.current={step,drawable,pending};
 const key=`prepcrew-device:${code}`;
 const savePending=(items:Pending[])=>{setPending(items);state.current.pending=items;try{if(items.length)sessionStorage.setItem(`${key}:pending`,JSON.stringify(items));else sessionStorage.removeItem(`${key}:pending`);}catch{setError(new Error('Device recovery storage is full. Keep this tab open until the strokes are saved.'));}};
 const strokes=strokesFromEvents(events.filter(e=>e.step===step));
 const visible=[...strokes,...pending.filter(p=>p.step===step&&!strokes.some(s=>s.id===p.stroke.id)).map(p=>p.stroke)];
 const latest=useRef(visible);latest.current=visible;
 const draw=()=>{const ctx=canvas.current?.getContext('2d');if(ctx)drawStrokes(ctx,[...latest.current,...draft.current?[draft.current]:[]]);};
 useEffect(draw,[JSON.stringify(visible)]);
 useEffect(()=>{const ctx=overlay.current?.getContext('2d');if(!ctx)return;ctx.clearRect(0,0,WIDTH,HEIGHT);if(review)try{drawMarks(ctx,validateMarks(review.annotations as Annotation[],visible));}catch{/* Revision no longer matches. */}},[review,JSON.stringify(visible)]);
 const remove=(all:boolean)=>{if(ws.current?.readyState===WebSocket.OPEN)ws.current.send(JSON.stringify({type:'remove',step,ids:(all?strokes:strokes.slice(-1)).map(s=>s.id)}));};
 useEffect(()=>{
  let disposed=false,timer:ReturnType<typeof setTimeout>,attempt=0;
  let token=sessionStorage.getItem(key);
  if(!token){token=randomId(32);sessionStorage.setItem(key,token);}
  try{const stored=JSON.parse(sessionStorage.getItem(`${key}:pending`)||'[]');if(Array.isArray(stored))savePending(stored.slice(0,100).filter(p=>Number.isInteger(p.step)&&schemas.Stroke.safeParse(p.stroke).success));}catch{sessionStorage.removeItem(`${key}:pending`);}
  const connect=()=>{
   const socket=new WebSocket(socketUrl(`/ws/v2/pair/${encodeURIComponent(code)}`));ws.current=socket;
   socket.onopen=()=>socket.send(JSON.stringify({type:'hello',token}));
   socket.onmessage=ev=>{
    if(disposed)return;
    try{
     const m=pairMessage.parse(JSON.parse(ev.data));
     if(m.type==='paired'){attempt=0;setStatus('Connected · syncing board');setError(null);}
     else if(m.type==='state'){
      if(m.step!==state.current.step)draft.current=null;
      setStep(m.step);setDrawable(m.drawable);state.current.step=m.step;state.current.drawable=m.drawable;
      setStatus(m.drawable?'Connected · ready to draw':'Connected · waiting for whiteboard');
      for(const item of state.current.pending)if(m.drawable&&item.step===m.step)socket.send(JSON.stringify({type:'stroke',...item}));
     }else if(m.type==='event'){
      const event=m.event as Event;
      setEvents(old=>[...old.filter(e=>e.seq!==event.seq),event].sort((a,b)=>a.seq-b.seq));
      if(event.kind==='stroke')savePending(state.current.pending.filter(p=>p.stroke.id!==event.payload.id));
     }
     else if(m.type==='ack')setError(null);
     else if(m.type==='review')setReview(m.review as Model<'BoardResult'>|null);
     else {setError(new Error(m.message));if(m.id)savePending(state.current.pending.filter(p=>p.stroke.id!==m.id));}
    }catch{setError(new Error('Invalid pairing response'));}
   };
   socket.onclose=ev=>{if(disposed)return;setDrawable(false);setStatus('Disconnected · reconnecting');if(ev.code===4404||ev.code===4400){setStatus('Pairing expired · request a new code');return;}timer=setTimeout(connect,Math.min(10000,500*2**attempt++));};
   socket.onerror=()=>setError(new Error('Connection interrupted. Pending strokes stay on this device until reconnect.'));
  };
  connect();return()=>{disposed=true;clearTimeout(timer);ws.current?.close();};
 },[code]);
 const point=(e:React.PointerEvent<HTMLCanvasElement>)=>{const r=e.currentTarget.getBoundingClientRect();return {x:Math.max(0,Math.min(WIDTH,(e.clientX-r.left)*WIDTH/r.width)),y:Math.max(0,Math.min(HEIGHT,(e.clientY-r.top)*HEIGHT/r.height)),pressure:e.pressure||.5};};
 return <Shell><main className="pair-page"><h1>Your whiteboard.</h1><p className="sub">Draw here. Talk to Dana on your laptop.</p>
  <Badge tone={drawable?'ok':'warn'}>{status}</Badge><ErrorNotice error={error}/>
  <div className="row top-gap">{(['path','rect','arrow'] as const).map(t=><Button key={t} size="sm" variant={tool===t?'default':'outline'} onClick={()=>setTool(t)}>{t==='path'?'Pen':t==='rect'?'Box':'Arrow'}</Button>)}<Button size="sm" variant="outline" disabled={!drawable||!!pending.length||!strokes.length} onClick={()=>remove(false)}>Undo</Button><Button size="sm" variant="outline" disabled={!drawable||!!pending.length||!strokes.length} onClick={()=>remove(true)}>Clear</Button></div>
  <div className="board-surface paired-board"><canvas ref={canvas} width={WIDTH} height={HEIGHT} aria-label="Paired iPad whiteboard"
   onPointerDown={e=>{if(!drawable||pending.length>=100)return;e.currentTarget.setPointerCapture(e.pointerId);draft.current={id:randomId(),kind:tool,points:[point(e)],label:''};draw();}}
   onPointerMove={e=>{if(!draft.current)return;const p=point(e);if(draft.current.kind==='path'){if(draft.current.points.length<10000)draft.current.points.push(p);}else draft.current.points=[draft.current.points[0],p];draw();}}
   onPointerUp={()=>{if(!draft.current)return;const item={stroke:draft.current,step:state.current.step};savePending([...state.current.pending,item]);if(ws.current?.readyState===WebSocket.OPEN)ws.current.send(JSON.stringify({type:'stroke',...item}));draft.current=null;draw();}}
   onPointerCancel={()=>{draft.current=null;draw();}}/><canvas ref={overlay} width={WIDTH} height={HEIGHT} className="annotation-layer" aria-label="Dana annotations"/></div>
  <p className="fine">Apple Pencil, touch, or mouse · {pending.length?`${pending.length} strokes awaiting confirmation`:'All strokes saved'} · reconnect works in this tab for up to 24 hours.</p>
 </main></Shell>;
}
