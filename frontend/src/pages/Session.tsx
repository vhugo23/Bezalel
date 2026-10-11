import { DanaOrb } from '../components/DanaOrb';
import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router';
import { api, eventMessage, openSessionSocket, type Event, type Model } from '../api/client';
import { useApp } from '../store';
import { useVoiceConversation } from '../lib/useVoiceConversation';
import type { LoadProgress } from '../lib/localSpeech';
import { Shell } from '../components/Shell';
import { Whiteboard } from '../components/Whiteboard';
import { PiLab, labReady } from '../components/PiLab';
import { DemoAutoplay } from '../components/DemoAutoplay';
import { QuitLesson, savedQuitPlan } from '../components/QuitLesson';
import { Badge, Button, ErrorNotice, Icon, Modal } from '../components/ui';

const labels = {off:'Ready when you are',connecting:'Connecting your microphone',loading:'Loading local speech',listening:'Listening to you',transcribing:'Transcribing your answer',thinking:'Dana is thinking',speaking:'Dana is speaking',muted:'Microphone muted'};

const size=(bytes:number)=>bytes>=1e9?`${(bytes/1e9).toFixed(2)} GB`:`${Math.round(bytes/1e6)} MB`;
function ModelProgress({progress:{model,stage,loaded,total,cached}}:{progress:LoadProgress}) {
  const percent=Math.min(99,Math.floor(100*loaded/total)),preparing=stage==='prepare';
  return <div className={`model-progress ${preparing?'preparing':''}`}>
    <div className="model-progress-head"><b>{preparing?`Starting ${model} on your GPU`:`${cached?'Loading':'Downloading'} ${model}`}</b><span>{preparing?'Almost ready':`${percent}%`}</span></div>
    <div className="model-progress-track" role="progressbar" aria-label={`${model} model`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={preparing?undefined:percent} aria-valuetext={preparing?'Starting on your GPU':`${percent}%`}><span style={{width:preparing?'100%':`${percent}%`}}/></div>
    <small>{preparing?'Model files are ready. First start can take a minute.':`${size(loaded)} of ${size(total)}${cached?' · saved on this device':''}`}</small>
  </div>;
}

export function SessionPage() {
  const {id=''}=useParams(); const nav=useNavigate(); const qc=useQueryClient();
  const sound=useApp(s=>s.voice);
  const [demoRunning,setDemoRunning]=useState(false),[demoCandidate,setDemoCandidate]=useState('');
  const [demoLabAction,setDemoLabAction]=useState<{kind:string;text:string}>();
  const [text,setText]=useState(''),[hideLoading,setHideLoading]=useState(false),[error,setError]=useState<unknown>(null),[connected,setConnected]=useState(false);
  const transcript=useRef<HTMLDivElement>(null),follow=useRef(true),autoFinished=useRef(false);
  const query=useQuery({queryKey:['session',id],queryFn:()=>api.session(id),refetchInterval:connected?false:3000});
  const session=query.data,step=session?.step??0,events=session?.events??[],steps=session?.steps??[];
  const isBoard=steps[step]?.surface==='whiteboard';
  const isLab=session?.engine_id==='linux_fault'&&step<steps.length;
  const turns=events.filter(e=>e.kind==='turn'||e.kind==='hint');
  const refresh=()=>qc.invalidateQueries({queryKey:['session',id]});
  const voice=useVoiceConversation({id,step,endStep:steps.length||10,demo:session?.demo??false,sound,onEvents:refresh,onError:setError});
  const next=useMutation({mutationFn:()=>api.append(id,{kind:'step',step:step+1,payload:{to:step+1}}),onSuccess:refresh,onError:setError});
  const pause=useMutation({mutationFn:()=>api.pause(id,!session?.paused),onSuccess:s=>{voice.end();qc.setQueryData(['session',id],s);},onError:setError});
  const hint=useMutation({mutationFn:()=>api.hint(id),onSuccess:refresh,onError:setError});
  useEffect(()=>{if(!voice.loadProgress)setHideLoading(false);},[voice.loadProgress]);
  const end=useMutation({mutationFn:()=>api.end(id),onSuccess:()=>nav(`/fleet/${id}`),onError:setError});

  useEffect(()=>{
    let disposed=false,timer:ReturnType<typeof setTimeout>,socket:WebSocket|undefined,after=0,attempt=0;
    const retry=()=>{if(!disposed)timer=setTimeout(()=>void connect(),Math.min(10000,500*2**attempt++));};
    const connect=async()=>{
      try{socket=await openSessionSocket(`/ws/v2/sessions/${id}?after=${after}`,id,'events');}
      catch{setConnected(false);retry();return;}
      if(disposed){socket.close();return;}
      socket.onopen=()=>{attempt=0;setConnected(true);};
      socket.onmessage=message=>{
        try{
          const event=eventMessage.parse(JSON.parse(message.data)).event as Event;after=Math.max(after,event.seq);
          qc.setQueryData<Model<'Session'>>(['session',id],old=>old?{...old,step:event.kind==='step'?Number(event.payload.to):old.step,paused:event.kind==='note'&&typeof event.payload.paused==='boolean'?event.payload.paused:old.paused,events:[...old.events.filter(e=>e.seq!==event.seq),event].sort((a,b)=>a.seq-b.seq)}:old);
          if(['command','edit','part_drop','probe','step'].includes(event.kind))void qc.invalidateQueries({queryKey:['session',id]});
        }catch{setError(new Error('The server sent an invalid session event.'));}
      };
      socket.onclose=()=>{setConnected(false);retry();};
    };
    void connect();return()=>{disposed=true;clearTimeout(timer);socket?.close();};
  },[id,qc]);
  useEffect(()=>{if(!demoRunning&&steps.length&&step===steps.length&&!autoFinished.current&&events.some(e=>e.kind==='step'&&e.payload.to===steps.length&&e.payload.source==='interviewer')){autoFinished.current=true;end.mutate();}},[step,events,steps.length,demoRunning]);
  useEffect(()=>{if(follow.current&&transcript.current)transcript.current.scrollTop=transcript.current.scrollHeight;},[turns.length,voice.phase,voice.partial,demoCandidate]);
  const submit=()=>{
    if(session?.paused||!text.trim()||next.isPending||(!voice.active&&voice.busy))return;
    const answer=text.trim();setText('');
    if(voice.active)voice.sendText(answer);else void voice.runText(()=>api.turn(id,{text:answer,step,board:isBoard}));
  };
  const startVoice=()=>{
    useApp.setState({voice:true});
    void voice.start(turns.filter(e=>e.actor==='interviewer').at(-1));
  };
  const hasAnswer=turns.some(e=>e.actor==='candidate'&&e.step===step);
  const done=(steps.length>0&&step>=steps.length)||session?.status==='graded';
  useEffect(()=>{if(session?.paused)voice.end();},[session?.paused]);
  // A quit session reopens on its saved next steps until the dialog is closed.
  const ended=session?.status==='ended';
  const [quitUi,setQuitUi]=useState<{id:string;open:boolean}|null>(null);
  const quitOpen=quitUi?.id===id?quitUi.open:ended;

  const conversation=<div className="voice-transcript" ref={transcript} role="log" aria-label="Interview transcript" aria-live="polite" onScroll={e=>{const el=e.currentTarget;follow.current=el.scrollHeight-el.scrollTop-el.clientHeight<70;}}>
    <div className="conversation-intro"><span>YOUR INTERVIEW</span><p>A conversation with Dana</p>{events.some(e=>e.payload.demo_autoplay===true)&&<small className="demo-candidate-label">Scripted demo candidate · graded from saved evidence</small>}</div>
    {turns.map(event=><article key={event.seq} className={`chat-turn ${event.actor==='interviewer'?'dana-turn':'candidate-turn'}`}>
      {event.actor==='interviewer'&&<span className="chat-avatar">D</span>}
      <div className="chat-message"><div className="chat-author">{event.actor==='interviewer'?'Dana':'You'}{event.payload.board===true&&<span>while drawing</span>}</div>
        <p>{String(event.payload.text)}</p>
        <div className="chat-meta"><span title="Saved session event">#{event.seq}</span>{events.some(e=>e.kind==='interrupted'&&e.payload.interrupted_seq===event.seq)&&<span>Interrupted</span>}{event.actor==='interviewer'&&event.kind==='turn'&&<button disabled={voice.busy} onClick={()=>{useApp.setState({voice:true});void voice.replay(event);}} aria-label={`Replay Dana's message ${event.seq}`}>Replay</button>}</div>
      </div>
    </article>)}
    {voice.partial&&<article className="chat-turn candidate-turn live-partial"><div className="chat-message"><div className="chat-author">You <span>live transcript</span></div><p>{voice.partial}<span className="transcript-caret"/></p></div></article>}
    {demoCandidate&&<article className="chat-turn candidate-turn live-partial"><div className="chat-message"><div className="chat-author">Demo candidate <span>speaking</span></div><p>{demoCandidate}</p></div></article>}
    {(voice.phase==='thinking'||voice.phase==='transcribing')&&<div className="conversation-pending" role="status"><span className="thinking-dots"><i/><i/><i/></span>{labels[voice.phase]}</div>}
  </div>;

  return <Shell crumb={`${({sw:'Software',hw:'Hardware',infra:'Infra',comm:'Communication',other:'Other'} as Record<string,string>)[session?.domain||'sw']} / ${session?.title||'Session'}`} exit wide>
    <main inert={demoRunning} className={`sgrid session-grid voice-session ${isBoard||isLab?'with-board':''} ${demoRunning?'demo-session-running':''}`}>
      <aside className="gcol">
        <section className="card"><div className="ch"><h3>Track</h3><Badge>{done?'Complete':`Step ${step+1} of ${steps.length}`}</Badge></div><div className="cb step-list">{steps.map(({title:name,surface},i)=><div className={`step ${i<step?'done':i===step?'cur':''}`} key={name}><span className="n">{i<step?<Icon name="check"/>:i+1}</span><div><b>{name}</b><small>{surface}</small></div></div>)}</div></section>
        <section className="card"><div className="cb"><div className="turn"><b>{ended?'Lesson ended':done?'Nicely done':'Your turn'}</b><span>{ended?'You ended this lesson early. Your transcript is saved.':steps[step]?.task||'Send the conversation and drawing to the evaluators.'}</span></div><div className="row session-actions">{ended?<Button size="sm" variant="outline" onClick={()=>setQuitUi({id,open:true})}>See next steps</Button>:!done?<><Button size="sm" disabled={next.isPending||voice.busy||isBoard||session?.paused||!hasAnswer||(isLab&&!labReady(session?.engine_state?.lab))} onClick={()=>next.mutate()}>Next step<Icon/></Button><Button size="sm" variant="outline" disabled={session?.status!=='live'||session?.paused||next.isPending} onClick={()=>setQuitUi({id,open:true})}>I don’t know</Button></>:<Button size="sm" disabled={end.isPending} onClick={()=>{voice.end();end.mutate();}}>{end.isPending?'Starting evaluators…':'Finish session'}<Icon/></Button>}</div></div></section>
        <div className="session-status"><span className={connected?'dotok':'dotwait'}/>{connected?'Conversation saved':'Reconnecting…'}<span className="fine">{events.length} events in your session</span></div>
        {session?.demo&&<p className="fine demo-note">Recorded demo replies. Your transcript and drawing are saved.</p>}
      </aside>
      <section className="card voice-stage">
        <header className="voice-header">
          <div className={`voice-presence ${voice.phase}`} title={voice.speechNote||undefined}><DanaOrb phase={voice.phase} level={voice.level} paused={!!session?.paused}/><div><b>Dana</b><span role="status">{demoRunning?(demoCandidate?'Demo candidate is speaking':voice.phase==='speaking'?'Dana is speaking':'Demo playback in progress'):session?.paused?'Interview paused · your work is saved':voice.active?labels[voice.phase]:session?.demo?'Recorded demo · press Start voice to talk':'Press Start voice to talk, or type below'}</span></div></div>
          {!done&&!ended&&<div className="voice-tools">
            {voice.active?<><button className={`icon-button ${voice.muted?'on':''}`} onClick={voice.toggleMute} aria-pressed={voice.muted} aria-label={voice.muted?'Unmute microphone':'Mute microphone'} title={voice.muted?'Unmute':'Mute'}><Icon name={voice.muted?'micOff':'mic'}/></button>{voice.phase==='speaking'?<button className="icon-button" onClick={voice.interrupt} aria-label="Interrupt Dana" title="Interrupt Dana"><Icon name="stop"/></button>:<button className="icon-button" onClick={voice.sendNow} disabled={voice.phase!=='listening'} aria-label="Send now" title="Send now — don’t wait for the pause"><Icon name="send"/></button>}<button className="icon-button danger" onClick={voice.end} aria-label="End voice" title="End voice"><Icon name="hangup"/></button></>:<Button size="sm" className="voice-start" onClick={startVoice} disabled={!session||voice.busy||session?.paused}><Icon name="mic"/>Start voice</Button>}
            <span className="voice-tools-divider"/>
            {!!steps[step]?.hints?.length&&<button className="icon-button" disabled={hint.isPending||session?.paused} onClick={()=>hint.mutate()} aria-label="Ask for a hint" title="Ask for a hint"><Icon name="bulb"/></button>}
            <button className="icon-button" disabled={pause.isPending} onClick={()=>pause.mutate()} aria-label={session?.paused?'Resume interview':'Pause interview'} title={session?.paused?'Resume interview':'Pause interview'}><Icon name={session?.paused?'play':'pause'}/></button>
          </div>}
        </header>
        <ErrorNotice error={error||query.error}/>
        <div className="session-surfaces">
          {isBoard&&!session?.paused&&<div className="drawing-panel"><Whiteboard key={`${id}:${step}`} lookMode={String(steps[step]?.config?.look||'on_done')} conversationBusy={voice.busy||voice.phase==='transcribing'||voice.level>0.12} partial={voice.partial} sid={id} step={step} continueLabel={`${steps[step+1]?.title||'Finish drawing'} →`} events={events} savedReview={session?.board_review} lookRequest={voice.lookRequest} onChange={refresh} onComplete={()=>next.mutate()} onSpeech={async mark=>{const current=await api.session(id);const event=current.events.find(e=>e.kind==='turn'&&e.payload.annotation_id===mark.id);return event?await voice.replay(event,false):false;}}/></div>}
          {isLab&&session&&<div className="drawing-panel"><PiLab key={id} session={session} onChange={refresh} demoAction={demoLabAction}/></div>}
          {conversation}
        </div>
        {!done&&!ended&&<footer className="voice-dock">
          <form className="comp one voice-composer" onSubmit={e=>{e.preventDefault();submit();}}><textarea aria-label="Your answer" rows={1} value={text} onChange={e=>setText(e.target.value)} placeholder={voice.active?'Or type to Dana…':isBoard?'Explain your drawing, or ask Dana a question…':'Message Dana…'} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submit();}}}/><Button size="sm" disabled={session?.paused||next.isPending||!text.trim()||(!voice.active&&voice.busy)}>Send</Button></form>
        </footer>}
        <Modal open={!!voice.loadProgress&&!hideLoading} onClose={()=>setHideLoading(true)} title="Setting up Dana’s voice" description={voice.speechNote||'Speech models run on this device.'}>
          {voice.loadProgress&&<ModelProgress progress={voice.loadProgress}/>}
          <p className="fine model-modal-note">Files are saved on this device, so this only downloads once. You can keep typing while it loads.</p>
          <div className="row model-modal-actions"><Button variant="ghost" size="sm" onClick={voice.end}>End voice</Button><Button size="sm" onClick={()=>setHideLoading(true)}>Keep typing</Button></div>
        </Modal>
        {session&&<QuitLesson key={id} sid={id} trackId={session.track_id} open={quitOpen} saved={savedQuitPlan(events)} onClose={()=>setQuitUi({id,open:false})} onResult={result=>{if(result.outcome==='ended')voice.end();void refresh();}}/>}
      </section>
    </main>
    {session&&<DemoAutoplay session={session} onRefresh={refresh} onStart={()=>{voice.end();useApp.setState({voice:true});}} onStop={voice.end} onRunning={setDemoRunning} onCandidate={setDemoCandidate} onLabAction={setDemoLabAction} speakDana={event=>voice.replay(event,true)} onFinish={()=>nav(`/fleet/${id}`)}/>}
  </Shell>;
}
