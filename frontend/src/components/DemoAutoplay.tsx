import { useEffect, useRef, useState } from 'react';
import { api, apiFetch, type Event, type Session } from '../api/client';
import { randomId } from '../lib/ids';
import { demoStep, demoBoardItems, demoBoardPng, supportsDemo } from '../lib/demoAutoplay';
import { activeItems, boardFromEvents } from '../lib/boardElements';
import './DemoAutoplay.css';

type Props={session:Session;onRefresh:()=>Promise<unknown>;onStart:()=>void;onStop:()=>void;onRunning:(running:boolean)=>void;onCandidate:(text:string)=>void;onLabAction:(action:{kind:string;text:string}|undefined)=>void;onFinish:()=>void;speakDana:(event:Event)=>Promise<boolean>};

/** A bounded, user-started rehearsal. Saved answers go through the ordinary grader. */
export function DemoAutoplay(props:Props){
 const latest=useRef(props);latest.current=props;
 const [running,setRunning]=useState(false),[status,setStatus]=useState(''),[error,setError]=useState('');
 const [voiceNote,setVoiceNote]=useState('');
 const run=useRef<{stopped:boolean;cancelSpeech?:()=>void}|null>(null);
 useEffect(()=>()=>{if(run.current){run.current.stopped=true;run.current.cancelSpeech?.();latest.current.onStop();}},[props.session.id]);
 const stop=()=>{if(run.current){run.current.stopped=true;run.current.cancelSpeech?.();}latest.current.onStop();setStatus('Stopping after the current saved action…');};
 const start=async()=>{
  if(run.current)return;
  const token={stopped:false,cancelSpeech:undefined as undefined|(()=>void)};run.current=token;
  setError('');setVoiceNote('');setStatus('Preparing the demo');setRunning(true);latest.current.onRunning(true);latest.current.onStart();
  const check=()=>{if(token.stopped)throw new DOMException('Playback stopped','AbortError');};
  const refresh=async()=>{await latest.current.onRefresh();check();};
  const candidate=async(text:string)=>{
   check();latest.current.onCandidate(text);setStatus('Demo candidate is speaking');
   if(!window.speechSynthesis){setVoiceNote('Candidate voice unavailable; answers appear as text.');return;}
   await new Promise<void>(resolve=>{
    const utterance=new SpeechSynthesisUtterance(text);
    const voices=window.speechSynthesis.getVoices().filter(v=>v.lang.startsWith('en'));
    utterance.voice=voices.find(v=>/david|daniel|guy|mark|male/i.test(v.name))||voices.at(-1)||null;
    utterance.pitch=.85;utterance.rate=1.08;
    const finish=()=>{clearTimeout(timeout);token.cancelSpeech=undefined;resolve();};
    const timeout=setTimeout(()=>{window.speechSynthesis.cancel();setVoiceNote('Candidate voice unavailable; continuing with text.');finish();},Math.max(8000,text.length*100));
    utterance.onend=finish;utterance.onerror=()=>{setVoiceNote('Candidate voice unavailable; continuing with text.');finish();};
    token.cancelSpeech=()=>{window.speechSynthesis.cancel();finish();};
    window.speechSynthesis.speak(utterance);
   });check();
  };
  const dana=async(event:Event)=>{
   check();setStatus('Dana is speaking');
   let timeout:ReturnType<typeof setTimeout>|undefined;
   const spoken=await Promise.race([latest.current.speakDana(event),new Promise<boolean>(resolve=>{timeout=setTimeout(()=>{latest.current.onStop();resolve(false);},60000);})]).finally(()=>clearTimeout(timeout));check();
   if(!spoken)setVoiceNote('Dana’s audio is unavailable; continuing with the saved transcript.');
   const response=await apiFetch(`/sessions/${props.session.id}/reply-complete`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({seq:event.seq})});
   if(!response.ok)throw new Error('Dana’s reply could not be saved. Stop and reopen the session to continue.');
   await refresh();
  };
  try{
   let current=await api.session(props.session.id);check();
   if(!supportsDemo(current))throw new Error('This changed scenario needs your own answers. Start either original track to watch the demo.');
   if(current.paused)throw new Error('Resume the interview before starting demo playback.');
   if(!current.events.some(e=>e.kind==='note'&&e.payload.demo_autoplay===true)){
    await api.append(current.id,{kind:'note',step:current.step,payload:{demo_autoplay:true,label:'Scripted demo candidate; real grading'}});await refresh();
   }
   if(!current.events.some(e=>e.actor==='candidate'&&e.kind==='turn')){
    const opening=current.events.filter(e=>e.actor==='interviewer'&&e.kind==='turn').at(-1);
    if(opening)await dana(opening);
   }else{
    const pending=current.events.filter(e=>e.actor==='interviewer'&&e.kind==='turn'&&e.step===current.step).at(-1);
    const lastAnswer=current.events.filter(e=>e.actor==='candidate'&&e.kind==='turn').at(-1);
    if(pending&&pending.seq>(lastAnswer?.seq??0)&&!current.events.some(e=>e.payload.reply_completed===pending.seq))await dana(pending);
   }
   // At most ten steps, each with a finite authored action/answer list. No polling loop.
   for(let iteration=0;iteration<10;iteration++){
    check();current=await api.session(current.id);check();
    if(current.step>=(current.steps?.length||0))break;
    const step=current.step,script=demoStep(current.engine_id,step);
    if(!script)throw new Error('Autoplay supports the original system design and Pi tracks. Continue this scenario yourself.');
    setStatus(`Step ${step+1}: ${current.steps?.[step].title}`);
    for(const action of script.actions){
     check();current=await api.session(current.id);check();if(current.step!==step)break;
     const lab=current.engine_state?.lab;
     const revision=lab&&typeof lab==='object'&&'revision' in lab?lab.revision:undefined;
     if(typeof revision!=='number')throw new Error('The Pi simulator state is unavailable. Your saved work is safe.');
     setStatus(`Candidate: ${action.kind==='edit'?'editing the configuration':action.text}`);
     latest.current.onLabAction(action);
     await new Promise(resolve=>setTimeout(resolve,650));check();
     await api.lab(current.id,{...action,step,revision,request_id:randomId()});await refresh();
    }
    if(script.board){
     check();current=await api.session(current.id);check();
     const savedIds=new Set(activeItems(boardFromEvents(current.events,step).latest).map(item=>item.id));
     const missing=(await demoBoardItems()).filter(item=>!savedIds.has(item.id));
     if(missing.length){
      setStatus('Candidate is drawing the design');
      for(const item of missing){
       check();await api.boardElements(current.id,{step,elements:[item]});await refresh();
       await new Promise(resolve=>setTimeout(resolve,300));
      }
     }
    }
    current=await api.session(current.id);check();
    const answered=new Set(current.events.filter(e=>e.actor==='candidate'&&e.kind==='turn'&&e.step===step).map(e=>e.payload.text));
    for(const answer of script.answers.filter(answer=>!answered.has(answer))){
     current=await api.session(current.id);check();if(current.step!==step)break;
     await candidate(answer);check();setStatus('Dana is thinking');
     const result=await api.turn(current.id,{text:answer,step,board:!!script.board});
     latest.current.onCandidate('');await refresh();
     for(const reply of result.events.filter(e=>e.actor==='interviewer'&&e.kind==='turn'))await dana(reply);
    }
    current=await api.session(current.id);check();
    if(current.step===step&&script.board&&!current.board_review){
     setStatus('Dana is reviewing the whiteboard');
     const items=activeItems(boardFromEvents(current.events,step).latest);
     const png=await demoBoardPng(items);check();await api.board(current.id,{elements:items,png});await refresh();
     current=await api.session(current.id);check();
     const reviewTurns=current.events.filter(e=>e.actor==='interviewer'&&e.kind==='turn'&&e.step===step&&e.payload.annotation_id);
     for(const reply of reviewTurns)await dana(reply);
    }
    current=await api.session(current.id);check();
    if(current.step===step){await api.append(current.id,{kind:'step',step:step+1,payload:{to:step+1}});await refresh();}
   }
   current=await api.session(props.session.id);check();
   if(current.step<(current.steps?.length||0))throw new Error('Playback stopped at the step limit. Continue the saved session manually.');
   setStatus('Sending the scripted session to the real graders');
   await api.end(current.id);check();latest.current.onFinish();
  }catch(e){if(!(e instanceof DOMException&&e.name==='AbortError'))setError(e instanceof Error?e.message:String(e));}
  finally{run.current=null;latest.current.onCandidate('');latest.current.onLabAction(undefined);latest.current.onStop();latest.current.onRunning(false);setRunning(false);setStatus('');void latest.current.onRefresh();}
 };
 if(!supportsDemo(props.session)||!demoStep(props.session.engine_id,props.session.step)||props.session.status!=='live')return null;
 return <aside className="demo-autoplay" aria-label="Demo playback">
  <div><b>Watch a practice session</b><small>Scripted candidate · real grading · saved to your history</small></div>
  {running?<button onClick={stop}>■ Stop & take over</button>:<button onClick={()=>void start()}>▶ Autoplay demo</button>}
  {running&&<p role="status">{status}</p>}
  {voiceNote&&<p>{voiceNote}</p>}{error&&<p role="alert">{error}</p>}
 </aside>;
}
