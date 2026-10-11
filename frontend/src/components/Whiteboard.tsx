import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api, type Annotation, type Event, type Stroke, type Model } from '../api/client';
import { schemas } from '../api/schemas';
import { drawMarks, drawStrokes, validateMarks, WIDTH, HEIGHT } from '../lib/board';
import { Badge, Button, ErrorNotice, Modal } from './ui';
import demoBoard from '../../../contracts/demo-board.json';
import QRCode from 'qrcode';
import { randomId, pairingLink } from '../lib/ids';
export function strokesFromEvents(events:Event[]):Stroke[]{
 const strokes=new Map<string,Stroke>();
 for(const e of events){if(e.kind==='stroke'&&e.actor==='candidate'){const s=schemas.Stroke.safeParse(e.payload);if(s.success)strokes.set((s.data as Stroke).id,s.data as Stroke);}if(e.kind==='note'&&Array.isArray(e.payload.remove_strokes)){e.payload.remove_strokes.forEach(id=>strokes.delete(String(id)));}}
 return [...strokes.values()];
}
export function Whiteboard({sid,events,onChange,onComplete,onSpeech,lookRequest=0,savedReview,lookMode='on_done',conversationBusy=false,partial='',step=1,continueLabel='Defend the trade-offs →'}:{sid:string;lookMode?:string;conversationBusy?:boolean;partial?:string;step?:number;continueLabel?:string;events:Event[];onChange:()=>Promise<unknown>;onComplete:()=>void;onSpeech:(mark:Annotation)=>Promise<boolean>;lookRequest?:number;savedReview?:Model<'BoardResult'>|null}){
 const canvas=useRef<HTMLCanvasElement>(null),overlay=useRef<HTMLCanvasElement>(null),draft=useRef<Stroke|null>(null),frame=useRef(0),alive=useRef(true);
 const [tool,setTool]=useState<'path'|'rect'|'arrow'>('path'),[busy,setBusy]=useState(false),[error,setError]=useState<unknown>(null),[marks,setMarks]=useState<Annotation[]>([]),[pairOpen,setPairOpen]=useState(false),[caption,setCaption]=useState('');
 const storageKey=`prepcrew-board:${sid}:${step}`;
 const [pending,setPending]=useState<Stroke[]>(()=>{try{const raw:unknown=JSON.parse(sessionStorage.getItem(storageKey)||'[]');if(!Array.isArray(raw))return [];return raw.slice(0,100).flatMap(item=>{const parsed=schemas.Stroke.safeParse(item);return parsed.success?[parsed.data as Stroke]:[];});}catch{return [];}}),[drawing,setDrawing]=useState(false),[reviewComplete,setReviewComplete]=useState(false),[qr,setQr]=useState(''),[pairOrigin,setPairOrigin]=useState(import.meta.env.VITE_PAIR_ORIGIN||location.origin);
 useEffect(()=>{try{if(pending.length)sessionStorage.setItem(storageKey,JSON.stringify(pending));else sessionStorage.removeItem(storageKey);}catch{setError(new Error('Local recovery storage is full. Keep this page open until the drawing is saved.'));}},[storageKey,pending]);
 const saved=useMemo(()=>strokesFromEvents(events.filter(e=>e.step===step)),[events,step]);
 const strokes=useMemo(()=>[...saved,...pending.filter(p=>!saved.some(s=>s.id===p.id))],[saved,pending]);
 const fingerprint=useMemo(()=>JSON.stringify(strokes),[strokes]);const latest=useRef(strokes);latest.current=strokes;
 useEffect(()=>{const ctx=canvas.current?.getContext('2d');if(ctx)drawStrokes(ctx,strokes);},[fingerprint]);
 useEffect(()=>{
  if(busy)return;
  if(!savedReview||JSON.stringify([...(savedReview.stroke_ids||[])].sort())!==JSON.stringify(strokes.map(s=>s.id).sort())){setMarks([]);setReviewComplete(false);overlay.current?.getContext('2d')?.clearRect(0,0,WIDTH,HEIGHT);setCaption('');return;}
  try{
   const checked=validateMarks(savedReview.annotations,strokes);
   setMarks(checked);setReviewComplete(true);const ctx=overlay.current?.getContext('2d');if(ctx)drawMarks(ctx,checked);
   setCaption(`Dana’s notes · ${savedReview.source==='recorded'?'recorded critique':'Gemini vision'}`);
  }catch{/* A changed drawing cannot reuse a critique of missing targets. */}
 },[savedReview?.artifact_id,busy,fingerprint]);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;cancelAnimationFrame(frame.current);};},[]);
 const pair=useMutation({mutationFn:()=>api.pair(sid)});
 const link=pair.data?pairingLink(pairOrigin,pair.data.code):'';
 useEffect(()=>{if(link)void QRCode.toDataURL(link,{width:200,margin:2}).then(setQr).catch(setError);else setQr('');},[link]);
 const save=async(s:Stroke)=>{setPending(old=>[...old.filter(p=>p.id!==s.id),s]);setError(null);try{await api.append(sid,{kind:'stroke',step,payload:s});await onChange();setPending(old=>old.filter(p=>p.id!==s.id));}catch(e){setError(e);}};
 const point=(e:React.PointerEvent<HTMLCanvasElement>)=>{const r=e.currentTarget.getBoundingClientRect();return {x:Math.max(0,Math.min(WIDTH,(e.clientX-r.left)*WIDTH/r.width)),y:Math.max(0,Math.min(HEIGHT,(e.clientY-r.top)*HEIGHT/r.height)),pressure:e.pressure||.5};};
 const down=(e:React.PointerEvent<HTMLCanvasElement>)=>{if(busy||reviewComplete)return;setDrawing(true);e.currentTarget.setPointerCapture(e.pointerId);draft.current={id:randomId(),kind:tool,points:[point(e)],label:''};};
 const move=(e:React.PointerEvent<HTMLCanvasElement>)=>{const d=draft.current;if(!d)return;const p=point(e);if(d.kind==='path'){if(d.points.length<10000)d.points.push(p);}else d.points=[d.points[0],p];const ctx=canvas.current?.getContext('2d');if(ctx)drawStrokes(ctx,[...strokes,d]);};
 const up=()=>{const d=draft.current;draft.current=null;setDrawing(false);if(d)void save(d);};
 const remove=async(all:boolean)=>{setBusy(true);try{await api.append(sid,{kind:'note',step,payload:{remove_strokes:(all?strokes:strokes.slice(-1)).map(s=>s.id)}});setMarks([]);setReviewComplete(false);overlay.current?.getContext('2d')?.clearRect(0,0,WIDTH,HEIGHT);await onChange();}catch(e){setError(e);}finally{setBusy(false);}};
 const sample=async()=>{setBusy(true);setError(null);try{if(strokes.length)await api.append(sid,{kind:'note',step,payload:{remove_strokes:strokes.map(s=>s.id)}});for(const raw of demoBoard)await api.append(sid,{kind:'stroke',step,payload:schemas.Stroke.parse(raw) as Stroke});await api.turn(sid,{step,board:true,text:'The limiter sits before the API service. I’m using a token bucket per API key, with shared counters in Redis.'});await onChange();}catch(e){setError(e);}finally{setBusy(false);}};
 const done=async()=>{if(!canvas.current||pending.length||drawing)return;setBusy(true);setError(null);setCaption('Dana is looking at your board…');try{const result=await api.board(sid,{strokes,png:canvas.current.toDataURL('image/png')});const checked=validateMarks(result.annotations,strokes);for(let i=0;i<checked.length;i++){if(!alive.current)return;setCaption(checked[i].speech);const speech=onSpeech(checked[i]);await new Promise<void>(resolve=>{const start=performance.now();const tick=(now:number)=>{if(!alive.current){resolve();return;}const progress=Math.min(1,(now-start)/900);const ctx=overlay.current?.getContext('2d');if(ctx)drawMarks(ctx,checked.slice(0,i+1),i,progress);if(progress<1)frame.current=requestAnimationFrame(tick);else resolve();};frame.current=requestAnimationFrame(tick);});if(!await speech)break;}if(!alive.current)return;setMarks(checked);setReviewComplete(true);setCaption(`Dana’s notes · ${result.source==='recorded'?'recorded critique':'Gemini vision'}`);await onChange();}catch(e){setError(e);setCaption('');}finally{if(alive.current)setBusy(false);}};
 const doneRef=useRef(done);doneRef.current=done;
 const attempted=useRef('');
 const lastSpeech=events.filter(e=>e.kind==='turn'&&e.actor==='candidate'&&e.step===step).at(-1)?.seq;
 useEffect(()=>{
  if(lookMode!=='on_pause'||busy||drawing||pending.length||reviewComplete||error||conversationBusy||partial||!strokes.length||attempted.current===fingerprint)return;
  const timer=setTimeout(()=>{attempted.current=fingerprint;void doneRef.current();},6000);return()=>clearTimeout(timer);
 },[lookMode,busy,drawing,pending.length,reviewComplete,error,conversationBusy,partial,fingerprint,lastSpeech]);
 const edit=async()=>{setBusy(true);try{await api.append(sid,{kind:'note',step,payload:{board_edit:true}});await onChange();setMarks([]);setReviewComplete(false);}catch(e){setError(e);}finally{setBusy(false);}};
 const looked=useRef(0);
 useEffect(()=>{if(lookRequest>looked.current&&!busy){looked.current=lookRequest;if(strokes.length&&!reviewComplete)void done();else if(!strokes.length)setError(new Error('Draw your design first, then ask Dana to look.'));}},[lookRequest,busy,strokes.length]);
 return <><div className="wbbar"><div className="seg"><button className="on">On this screen</button><button onClick={()=>{setPairOpen(true);if(!pair.data)pair.mutate();}}>On my iPad</button></div><span className="grow"/><div className="seg" role="group" aria-label="Drawing tools">{(['path','rect','arrow'] as const).map(t=><button disabled={busy||reviewComplete} aria-pressed={tool===t} className={tool===t?'on':''} key={t} onClick={()=>setTool(t)}>{t==='path'?'Pen':t==='rect'?'Box':'Arrow'}</button>)}</div><div className="wbtools"><Button variant="outline" size="sm" disabled={!strokes.length||busy||!!pending.length} onClick={()=>remove(false)}>Undo</Button><Button variant="outline" size="sm" disabled={!strokes.length||busy||!!pending.length} onClick={()=>remove(true)}>Clear</Button><Button size="sm" disabled={!strokes.length||busy||!!pending.length||reviewComplete} onClick={done}>Done, take a look</Button></div></div>
 <div className="board-area"><div className="board-surface"><canvas ref={canvas} width={WIDTH} height={HEIGHT} aria-label="Candidate whiteboard, draw using your pointer" onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={()=>{draft.current=null;setDrawing(false);const ctx=canvas.current?.getContext('2d');if(ctx)drawStrokes(ctx,strokes);}}/><canvas ref={overlay} width={WIDTH} height={HEIGHT} className="annotation-layer" aria-label="Dana’s annotations, separate from your drawing"/></div>{caption&&<div className={`board-caption ${busy?'looking':''}`} role="status">{busy&&<span className="spin"/>}{caption}</div>}</div>
 <div className="board-footer"><span className="fine">900 × 540 · {saved.length} saved strokes{pending.length?` · ${pending.length} awaiting save`:''} · Dana’s marks stay separate</span>{reviewComplete?<div className="row"><Button size="sm" variant="outline" disabled={busy} onClick={edit}>Edit drawing</Button><Button size="sm" onClick={onComplete}>{continueLabel}</Button></div>:<Button variant="ghost" size="sm" disabled={busy||!!pending.length} onClick={sample}>Load demo board + explanation</Button>}</div><ErrorNotice error={error}/>{!!pending.length&&!busy&&<Button variant="outline" size="sm" onClick={()=>{for(const stroke of pending)void save(stroke);}}>Retry unsaved strokes</Button>}{!!error&&strokes.length>0&&!busy&&!pending.length&&<Button variant="outline" size="sm" onClick={async()=>{await api.append(sid,{kind:'note',step,payload:{critique_skipped:true}});onComplete();}}>Continue without critique</Button>}
 <Modal open={pairOpen} onClose={()=>setPairOpen(false)} title="Draw on your iPad" description="Open the pairing link on your iPad on the same network. This code expires after 10 minutes and works once."><ErrorNotice error={pair.error}/>{pair.data?<>{qr&&<img src={qr} width={200} height={200} alt="Scan to pair this whiteboard"/>}<p className="pair-code">{pair.data.code}</p><label className="fine">Address your iPad can reach<input aria-label="Pairing origin" className="field" value={pairOrigin} onChange={e=>setPairOrigin(e.target.value)} placeholder="https://your-app.example"/></label><p className="fine">Pairing link</p><a className="pair-link" href={link||undefined} target="_blank" rel="noreferrer">{link||'Enter a valid HTTP or HTTPS origin'}</a><p className="fine top-gap">For a physical iPad, use your computer’s LAN address with HTTPS. A localhost link works only on this computer.</p><Button variant="outline" size="sm" onClick={()=>pair.mutate()}>Generate a new code</Button></>:<p className="top-gap">Creating a pairing code…</p>}</Modal></>;
}
