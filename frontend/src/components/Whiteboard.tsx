import { useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api, type Annotation, type Event, type Stroke, type Model } from '../api/client';
import { schemas } from '../api/schemas';
import { drawMarks, drawStrokes, validateMarks, WIDTH, HEIGHT } from '../lib/board';
import { Badge, Button, ErrorNotice, Modal } from './ui';
import demoBoard from '../../../contracts/demo-board.json';
export function strokesFromEvents(events:Event[]):Stroke[]{
 const strokes=new Map<string,Stroke>();
 for(const e of events){if(e.kind==='stroke'&&e.actor==='candidate'){const s=schemas.Stroke.safeParse(e.payload);if(s.success)strokes.set((s.data as Stroke).id,s.data as Stroke);}if(e.kind==='note'&&Array.isArray(e.payload.remove_strokes)){e.payload.remove_strokes.forEach(id=>strokes.delete(String(id)));}}
 return [...strokes.values()];
}
export function Whiteboard({sid,events,onChange,onComplete,onSpeech,lookRequest=0,savedReview}:{sid:string;events:Event[];onChange:()=>Promise<unknown>;onComplete:()=>void;onSpeech:(mark:Annotation)=>Promise<boolean>;lookRequest?:number;savedReview?:Model<'BoardResult'>|null}){
 const canvas=useRef<HTMLCanvasElement>(null),overlay=useRef<HTMLCanvasElement>(null),draft=useRef<Stroke|null>(null),frame=useRef(0),alive=useRef(true);
 const [tool,setTool]=useState<'path'|'rect'|'arrow'>('path'),[busy,setBusy]=useState(false),[error,setError]=useState<unknown>(null),[marks,setMarks]=useState<Annotation[]>([]),[pairOpen,setPairOpen]=useState(false),[caption,setCaption]=useState('');
 const strokes=strokesFromEvents(events);const latest=useRef(strokes);latest.current=strokes;
 useEffect(()=>{const ctx=canvas.current?.getContext('2d');if(ctx)drawStrokes(ctx,strokes);},[JSON.stringify(strokes)]);
 useEffect(()=>{
  if(busy||!savedReview)return;
  try{
   const checked=validateMarks(savedReview.annotations,strokes);
   setMarks(checked);const ctx=overlay.current?.getContext('2d');if(ctx)drawMarks(ctx,checked);
   setCaption(`Dana’s notes · ${savedReview.source==='recorded'?'recorded critique':'Gemini vision'}`);
  }catch{/* A changed drawing cannot reuse a critique of missing targets. */}
 },[savedReview?.artifact_id,busy]);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;cancelAnimationFrame(frame.current);};},[]);
 const pair=useMutation({mutationFn:()=>api.pair(sid)});
 const save=async(s:Stroke)=>{setBusy(true);setError(null);try{await api.append(sid,{kind:'stroke',step:1,payload:s});await onChange();}catch(e){setError(e);}finally{setBusy(false);const ctx=canvas.current?.getContext('2d');if(ctx)drawStrokes(ctx,latest.current);}};
 const point=(e:React.PointerEvent<HTMLCanvasElement>)=>{const r=e.currentTarget.getBoundingClientRect();return {x:Math.max(0,Math.min(WIDTH,(e.clientX-r.left)*WIDTH/r.width)),y:Math.max(0,Math.min(HEIGHT,(e.clientY-r.top)*HEIGHT/r.height)),pressure:e.pressure||.5};};
 const down=(e:React.PointerEvent<HTMLCanvasElement>)=>{if(busy||marks.length)return;e.currentTarget.setPointerCapture(e.pointerId);draft.current={id:crypto.randomUUID(),kind:tool,points:[point(e)],label:''};};
 const move=(e:React.PointerEvent<HTMLCanvasElement>)=>{const d=draft.current;if(!d)return;const p=point(e);if(d.kind==='path'){if(d.points.length<10000)d.points.push(p);}else d.points=[d.points[0],p];const ctx=canvas.current?.getContext('2d');if(ctx)drawStrokes(ctx,[...strokes,d]);};
 const up=()=>{const d=draft.current;draft.current=null;if(d)void save(d);};
 const remove=async(all:boolean)=>{setBusy(true);try{await api.append(sid,{kind:'note',step:1,payload:{remove_strokes:(all?strokes:strokes.slice(-1)).map(s=>s.id)}});setMarks([]);overlay.current?.getContext('2d')?.clearRect(0,0,WIDTH,HEIGHT);await onChange();}catch(e){setError(e);}finally{setBusy(false);}};
 const sample=async()=>{setBusy(true);setError(null);try{if(strokes.length)await api.append(sid,{kind:'note',step:1,payload:{remove_strokes:strokes.map(s=>s.id)}});for(const raw of demoBoard)await api.append(sid,{kind:'stroke',step:1,payload:schemas.Stroke.parse(raw) as Stroke});await api.turn(sid,{step:1,board:true,text:'The limiter sits before the API service. I’m using a token bucket per API key, with shared counters in Redis.'});await onChange();}catch(e){setError(e);}finally{setBusy(false);}};
 const done=async()=>{if(!canvas.current)return;setBusy(true);setError(null);setCaption('Dana is looking at your board…');try{const result=await api.board(sid,{strokes,png:canvas.current.toDataURL('image/png')});const checked=validateMarks(result.annotations,strokes);for(let i=0;i<checked.length;i++){if(!alive.current)return;setCaption(checked[i].speech);const speech=onSpeech(checked[i]);await new Promise<void>(resolve=>{const start=performance.now();const tick=(now:number)=>{if(!alive.current){resolve();return;}const progress=Math.min(1,(now-start)/900);const ctx=overlay.current?.getContext('2d');if(ctx)drawMarks(ctx,checked.slice(0,i+1),i,progress);if(progress<1)frame.current=requestAnimationFrame(tick);else resolve();};frame.current=requestAnimationFrame(tick);});if(!await speech)break;}if(!alive.current)return;setMarks(checked);setCaption(`Dana’s notes · ${result.source==='recorded'?'recorded critique':'Gemini vision'}`);await onChange();}catch(e){setError(e);setCaption('');}finally{if(alive.current)setBusy(false);}};
 const looked=useRef(0);
 useEffect(()=>{if(lookRequest>looked.current&&!busy){looked.current=lookRequest;if(strokes.length&&!marks.length)void done();else if(!strokes.length)setError(new Error('Draw your design first, then ask Dana to look.'));}},[lookRequest,busy,strokes.length]);
 return <><div className="wbbar"><div className="seg"><button className="on">On this screen</button><button onClick={()=>{setPairOpen(true);if(!pair.data)pair.mutate();}}>On my iPad</button></div><span className="grow"/><div className="seg" role="group" aria-label="Drawing tools">{(['path','rect','arrow'] as const).map(t=><button disabled={busy||!!marks.length} aria-pressed={tool===t} className={tool===t?'on':''} key={t} onClick={()=>setTool(t)}>{t==='path'?'Pen':t==='rect'?'Box':'Arrow'}</button>)}</div><div className="wbtools"><Button variant="outline" size="sm" disabled={!strokes.length||busy} onClick={()=>remove(false)}>Undo</Button><Button variant="outline" size="sm" disabled={!strokes.length||busy} onClick={()=>remove(true)}>Clear</Button><Button size="sm" disabled={!strokes.length||busy||!!marks.length} onClick={done}>Done, take a look</Button></div></div>
 <div className="board-area"><div className="board-surface"><canvas ref={canvas} width={WIDTH} height={HEIGHT} aria-label="Candidate whiteboard, draw using your pointer" onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={()=>{draft.current=null;const ctx=canvas.current?.getContext('2d');if(ctx)drawStrokes(ctx,strokes);}}/><canvas ref={overlay} width={WIDTH} height={HEIGHT} className="annotation-layer" aria-label="Dana’s annotations, separate from your drawing"/></div>{caption&&<div className={`board-caption ${busy?'looking':''}`} role="status">{busy&&<span className="spin"/>}{caption}</div>}</div>
 <div className="board-footer"><span className="fine">900 × 540 · {strokes.length} saved strokes · Dana’s marks stay separate</span>{marks.length?<Button size="sm" onClick={onComplete}>Defend the trade-offs →</Button>:<Button variant="ghost" size="sm" disabled={busy} onClick={sample}>Load demo board + explanation</Button>}</div><ErrorNotice error={error}/>{!!error&&strokes.length>0&&!busy&&<Button variant="outline" size="sm" onClick={async()=>{await api.append(sid,{kind:'note',step:1,payload:{critique_skipped:true}});onComplete();}}>Continue without critique</Button>}
 <Modal open={pairOpen} onClose={()=>setPairOpen(false)} title="Draw on your iPad" description="Open the pairing link on your iPad on the same network. This code expires after 10 minutes and works once."><ErrorNotice error={pair.error}/>{pair.data?<><p className="pair-code">{pair.data.code}</p><p className="fine">Pairing link</p><a className="pair-link" href={`/pair/${pair.data.code}`} target="_blank" rel="noreferrer">{location.origin}/pair/{pair.data.code}</a><p className="fine top-gap">For a physical iPad, use your computer’s LAN address with HTTPS. A localhost link works only on this computer.</p></>:<p className="top-gap">Creating a pairing code…</p>}</Modal></>;
}
