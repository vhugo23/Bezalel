import { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api, type Annotation, type Event, type Model, type Stroke } from '../api/client';
import { schemas } from '../api/schemas';
import { MAX_BATCH, activeItems, boardFingerprint, boardFromEvents, danaSkeletons, legacyToSkeletons, mergePending, parseItem, toItem, validateMarks, type BoardItem } from '../lib/boardElements';
import type { BoardHandle } from './BoardCanvas';
import { Button, ErrorNotice, Modal } from './ui';
import demoBoard from '../../../contracts/demo-board.json';
import QRCode from 'qrcode';
import { pairingLink } from '../lib/ids';

const BoardCanvas=lazy(()=>import('./BoardCanvas'));
export const boardLoading=<div className="board-loading" role="status">Loading the whiteboard…</div>;

export function Whiteboard({sid,events,onChange,onComplete,onSpeech,lookRequest=0,savedReview,lookMode='on_done',conversationBusy=false,partial='',step=1,continueLabel='Defend the trade-offs →'}:{sid:string;lookMode?:string;conversationBusy?:boolean;partial?:string;step?:number;continueLabel?:string;events:Event[];onChange:()=>Promise<unknown>;onComplete:()=>void;onSpeech:(mark:Annotation)=>Promise<boolean>;lookRequest?:number;savedReview?:Model<'BoardResult'>|null}){
 const canvas=useRef<BoardHandle|null>(null),alive=useRef(true),saving=useRef<Promise<void>>(Promise.resolve());
 const [busy,setBusy]=useState(false),[error,setError]=useState<unknown>(null),[saveError,setSaveError]=useState(''),[marks,setMarks]=useState<Annotation[]>([]),[shown,setShown]=useState(0),[pairOpen,setPairOpen]=useState(false),[caption,setCaption]=useState('');
 const [drawing,setDrawing]=useState(false),[reviewComplete,setReviewComplete]=useState(false),[qr,setQr]=useState(''),[pairOrigin,setPairOrigin]=useState(import.meta.env.VITE_PAIR_ORIGIN||location.origin);
 const storageKey=`prepcrew-board:${sid}:${step}`;
 const [pending,setPendingState]=useState<BoardItem[]>(()=>{try{const raw:unknown=JSON.parse(sessionStorage.getItem(storageKey)||'[]');return Array.isArray(raw)?raw.slice(0,2000).flatMap(item=>{const parsed=parseItem(item);return parsed?[parsed]:[];}):[];}catch{return [];}});
 const pendingRef=useRef(pending);
 const setPending=(update:(old:BoardItem[])=>BoardItem[])=>{const next=update(pendingRef.current);pendingRef.current=next;setPendingState(next);};
 useEffect(()=>{try{if(pending.length)sessionStorage.setItem(storageKey,JSON.stringify(pending));else sessionStorage.removeItem(storageKey);}catch{setError(new Error('Local recovery storage is full. Keep this page open until the drawing is saved.'));}},[storageKey,pending]);
 const {latest,legacy}=useMemo(()=>boardFromEvents(events,step),[events,step]);
 // A saved version (ours, or a newer one from the paired iPad) settles the pending edit.
 useEffect(()=>{if(pendingRef.current.some(p=>(latest.get(p.id)?.version??0)>=p.version))setPending(old=>old.filter(p=>(latest.get(p.id)?.version??0)<p.version));},[latest]);
 const items=useMemo(()=>activeItems(latest),[latest]);
 const fingerprint=boardFingerprint(items);
 const legacySkeletons=useMemo(()=>legacyToSkeletons(legacy),[legacy]);
 const overlay=useMemo(()=>danaSkeletons(marks.slice(0,shown)),[marks,shown]);
 useEffect(()=>{
  if(busy)return;
  if(!savedReview||[...(savedReview.stroke_ids||[])].sort().join('|')!==items.map(i=>i.id).sort().join('|')){setMarks([]);setShown(0);setReviewComplete(false);setCaption('');return;}
  try{
   const checked=validateMarks(savedReview.annotations,items);
   setMarks(checked);setShown(checked.length);setReviewComplete(true);
   setCaption(`Dana’s notes · ${savedReview.source==='recorded'?'recorded critique':'Gemini vision'}`);
  }catch{/* A changed drawing cannot reuse a critique of missing targets. */}
 },[savedReview?.artifact_id,busy,fingerprint]);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 const pair=useMutation({mutationFn:()=>api.pair(sid)});
 const link=pair.data?pairingLink(pairOrigin,pair.data.code):'';
 useEffect(()=>{if(link)void QRCode.toDataURL(link,{width:200,margin:2}).then(setQr).catch(setError);else setQr('');},[link]);

 const send=async(batch:readonly BoardItem[])=>{for(let i=0;i<batch.length;i+=MAX_BATCH)await api.boardElements(sid,{step,elements:batch.slice(i,i+MAX_BATCH)});};
 const prune=(saved:ReadonlyMap<string,BoardItem>)=>setPending(old=>old.filter(p=>(saved.get(p.id)?.version??0)<p.version));
 const flushPending=():Promise<void>=>saving.current=saving.current.then(async()=>{
  for(let attempt=0;attempt<2&&pendingRef.current.length;attempt++){
   try{await send(pendingRef.current);setSaveError('');await onChange();return;}
   catch(e){
    // A stale version (the iPad saved first) is settled by the server's copy; anything else stays queued.
    try{prune(boardFromEvents((await api.session(sid)).events,step).latest);}catch{/* keep everything queued */}
    void onChange().catch(()=>{});
    if(attempt===1&&pendingRef.current.length)setSaveError(e instanceof Error?e.message:String(e));
   }
  }
 });
 const save=(changed:BoardItem[])=>{setPending(old=>mergePending(old,changed));void flushPending();};

 const done=async()=>{
  if(busy||drawing)return;
  setBusy(true);setError(null);setCaption('Dana is looking at your board…');
  try{
   canvas.current?.flush();await saving.current;
   if(pendingRef.current.length)throw new Error('Some drawing changes are not saved yet. Retry saving, then ask Dana again.');
   // Review exactly what the server holds, not what this tab believes it saved.
   const current=await api.session(sid);
   const snapshot=activeItems(boardFromEvents(current.events,step).latest);
   if(!snapshot.length)throw new Error('Draw your design first, then ask Dana to look.');
   const png=await canvas.current!.exportPng();
   const result=await api.board(sid,{elements:snapshot,png});
   const checked=validateMarks(result.annotations,snapshot);
   setMarks(checked);
   for(let i=0;i<checked.length;i++){if(!alive.current)return;setShown(i+1);setCaption(checked[i].speech);if(!await onSpeech(checked[i]))break;}
   if(!alive.current)return;
   setShown(checked.length);setReviewComplete(true);setCaption(`Dana’s notes · ${result.source==='recorded'?'recorded critique':'Gemini vision'}`);await onChange();
  }catch(e){setError(e);setCaption('');}finally{if(alive.current)setBusy(false);}
 };
 const doneRef=useRef(done);doneRef.current=done;
 const attempted=useRef('');
 const lastSpeech=events.filter(e=>e.kind==='turn'&&e.actor==='candidate'&&e.step===step).at(-1)?.seq;
 useEffect(()=>{
  if(lookMode!=='on_pause'||busy||drawing||pending.length||reviewComplete||error||conversationBusy||partial||!items.length||attempted.current===fingerprint)return;
  const timer=setTimeout(()=>{attempted.current=fingerprint;void doneRef.current();},6000);return()=>clearTimeout(timer);
 },[lookMode,busy,drawing,pending.length,reviewComplete,error,conversationBusy,partial,fingerprint,lastSpeech]);
 const edit=async()=>{setBusy(true);try{await api.append(sid,{kind:'note',step,payload:{board_edit:true}});await onChange();setMarks([]);setShown(0);setReviewComplete(false);}catch(e){setError(e);}finally{setBusy(false);}};
 const sample=async()=>{
  if(!canvas.current)return;
  setBusy(true);setError(null);
  try{
   await saving.current;
   // Measure labels in the board's handwriting font, not the fallback it shows before the font arrives.
   await Promise.all([16,14].map(size=>document.fonts.load(`${size}px Excalifont`))).catch(()=>{});
   const demo=canvas.current.convert(legacyToSkeletons(demoBoard.map(raw=>schemas.Stroke.parse(raw) as Stroke)));
   const ids=new Set(demo.map(e=>e.id));
   // Replace the board: delete what is there, and draw the demo above any saved version of its ids.
   const cleared=items.filter(i=>!ids.has(i.id)).map(i=>toItem({...i.element,isDeleted:true,version:i.version+1,versionNonce:Math.floor(Math.random()*2**31)}));
   const fresh=demo.map(e=>toItem({...e,version:(latest.get(e.id)?.version??0)+1}));
   await send([...cleared,...fresh]);
   await api.turn(sid,{step,board:true,text:'The limiter sits before the API service. I’m using a token bucket per API key, with shared counters in Redis.'});
   await onChange();
  }catch(e){setError(e);}finally{setBusy(false);}
 };
 const looked=useRef(0);
 useEffect(()=>{if(lookRequest>looked.current&&!busy){looked.current=lookRequest;if(items.length&&!reviewComplete)void done();else if(!items.length)setError(new Error('Draw your design first, then ask Dana to look.'));}},[lookRequest,busy,items.length]);

 return <><div className="wbbar"><div className="seg"><button className="on">On this screen</button><button onClick={()=>{setPairOpen(true);if(!pair.data)pair.mutate();}}>On my iPad</button></div><span className="grow"/><div className="wbtools"><Button size="sm" disabled={!items.length||busy||drawing||!!pending.length||reviewComplete} onClick={done}>Done, take a look</Button></div></div>
 <div className="board-area"><div className="board-surface board-excalidraw"><Suspense fallback={boardLoading}><BoardCanvas ref={canvas} label="Candidate whiteboard" saved={latest} extra={legacySkeletons} overlay={overlay} readOnly={busy||reviewComplete} onEdit={save} onInteracting={setDrawing} onUnsupported={()=>setError(new Error('Frames and embedded pages aren’t kept on this board. Use shapes, arrows, lines and text.'))} saveState={saveError&&pending.length?'failed':pending.length?'saving':'saved'} saveError={saveError} onRetry={()=>void flushPending()} onDemo={busy||reviewComplete||pending.length?undefined:()=>void sample()}/></Suspense></div>{caption&&<div className={`board-caption ${busy?'looking':''}`} role="status">{busy&&<span className="spin"/>}{caption}</div>}</div>
 {reviewComplete&&<div className="board-footer"><span className="grow"/><div className="row"><Button size="sm" variant="outline" disabled={busy} onClick={edit}>Edit drawing</Button><Button size="sm" onClick={onComplete}>{continueLabel}</Button></div></div>}<ErrorNotice error={error}/>{!!error&&items.length>0&&!busy&&!pending.length&&<Button variant="outline" size="sm" onClick={async()=>{await api.append(sid,{kind:'note',step,payload:{critique_skipped:true}});onComplete();}}>Continue without critique</Button>}
 <Modal open={pairOpen} onClose={()=>setPairOpen(false)} title="Draw on your iPad" description="Open the pairing link on your iPad on the same network. This code expires after 10 minutes and works once."><ErrorNotice error={pair.error}/>{pair.data?<>{qr&&<img src={qr} width={200} height={200} alt="Scan to pair this whiteboard"/>}<p className="pair-code">{pair.data.code}</p><label className="fine">Address your iPad can reach<input aria-label="Pairing origin" className="field" value={pairOrigin} onChange={e=>setPairOrigin(e.target.value)} placeholder="https://your-app.example"/></label><p className="fine">Pairing link</p><a className="pair-link" href={link||undefined} target="_blank" rel="noreferrer">{link||'Enter a valid HTTP or HTTPS origin'}</a><p className="fine top-gap">For a physical iPad, use your computer’s LAN address with HTTPS. A localhost link works only on this computer.</p><Button variant="outline" size="sm" onClick={()=>pair.mutate()}>Generate a new code</Button></>:<p className="top-gap">Creating a pairing code…</p>}</Modal></>;
}
