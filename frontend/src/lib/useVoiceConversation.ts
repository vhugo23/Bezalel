import { useEffect, useRef, useState } from 'react';
import { API, api, socketUrl, type Event, type Model } from '../api/client';
import { voiceMessage } from './voiceProtocol';

export type VoicePhase='off'|'connecting'|'listening'|'transcribing'|'thinking'|'speaking'|'muted';
type Options={id:string;step:number;demo:boolean;sound:boolean;onEvents:()=>Promise<unknown>;onError:(e:unknown)=>void};

export function useVoiceConversation(options:Options) {
  const opts=useRef(options);opts.current=options;
  const [phase,setPhase]=useState<VoicePhase>('off'),[active,setActive]=useState(false),[muted,setMuted]=useState(false),[level,setLevel]=useState(0);
  const [partial,setPartial]=useState(''),[lookRequest,setLookRequest]=useState(0);
  const state=useRef({alive:true,active:false,muted:false,epoch:0,revision:0,starting:false});
  const socket=useRef<WebSocket|null>(null),media=useRef<MediaStream|null>(null),context=useRef<AudioContext|null>(null),worklet=useRef<AudioWorkletNode|null>(null);
  const audio=useRef<HTMLAudioElement|null>(null),finish=useRef<((completed:boolean)=>void)|null>(null);
  const replayWaiter=useRef<{seq:number;resolve:(completed:boolean)=>void}|null>(null);
  const timer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
  const setStatus=(p:VoicePhase)=>{if(state.current.alive)setPhase(p);};
  const idle=()=>setStatus(state.current.active?(state.current.muted?'muted':'listening'):'off');
  const send=(message:Record<string,unknown>)=>{if(socket.current?.readyState===WebSocket.OPEN)socket.current.send(JSON.stringify(message));};
  const stopAudio=()=>{
    const clip=audio.current;audio.current=null;
    if(clip){clip.onended=null;clip.onerror=null;clip.pause();clip.removeAttribute('src');clip.load();}
    window.speechSynthesis?.cancel();
    const done=finish.current;finish.current=null;done?.(false);
  };
  const end=()=>{
    state.current.epoch++;state.current.active=false;state.current.starting=false;
    clearTimeout(timer.current);send({type:'stop'});
    const ws=socket.current;socket.current=null;if(ws){ws.onclose=null;ws.onmessage=null;ws.close();}
    stopAudio();replayWaiter.current?.resolve(false);replayWaiter.current=null;worklet.current?.disconnect();worklet.current=null;
    media.current?.getTracks().forEach(t=>t.stop());media.current=null;
    void context.current?.close();context.current=null;
    state.current.muted=false;
    if(state.current.alive){setActive(false);setMuted(false);setLevel(0);setPartial('');setStatus('off');}
  };
  const say=async(event:Event,force=false):Promise<boolean>=>{
    stopAudio();
    if(!opts.current.sound&&!force)return true;
    setStatus('speaking');
    return new Promise<boolean>((resolve,reject)=>{
      const complete=()=>{finish.current=null;audio.current=null;resolve(true);};
      finish.current=resolve;
      if(opts.current.demo){
        const u=new SpeechSynthesisUtterance(String(event.payload.text));u.onend=complete;u.onerror=()=>{finish.current=null;resolve(false);};speechSynthesis.speak(u);
      }else{
        const clip=new Audio(`${API}/api/v2/sessions/${opts.current.id}/speech/${event.seq}`);audio.current=clip;
        const failed=()=>{if(audio.current!==clip)return;audio.current=null;finish.current=null;reject(new Error('Dana’s audio could not play. The transcript is saved; use Replay to try again.'));};
        clip.onended=complete;clip.onerror=failed;void clip.play().catch(failed);
      }
    });
  };
  const playReply=async(event:Event,revision:number,epoch:number)=>{
    if(revision<state.current.revision)return;
    state.current.revision=revision;
    try{
      send({type:'playback_started',seq:event.seq,revision});
      const completed=await say(event);
      if(replayWaiter.current?.seq===event.seq){replayWaiter.current.resolve(completed);replayWaiter.current=null;}
      if(epoch!==state.current.epoch||revision!==state.current.revision)return;
      if(completed)send({type:'playback_done',seq:event.seq,revision});
      idle();
    }catch(e){
      if(replayWaiter.current?.seq===event.seq){replayWaiter.current.resolve(false);replayWaiter.current=null;}
      if(epoch===state.current.epoch){send({type:'playback_failed',seq:event.seq,revision});opts.current.onError(e);idle();}
    }
  };
  const start=async(opening?:Event)=>{
    if(state.current.active||state.current.starting)return;
    state.current.starting=true;state.current.revision=0;setStatus('connecting');opts.current.onError(null);
    const epoch=++state.current.epoch;
    try{
      if(opts.current.demo)throw new Error('Realtime voice requires live mode on the server.');
      if(!navigator.mediaDevices?.getUserMedia)throw new Error('Microphone access requires HTTPS or localhost.');
      const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      if(epoch!==state.current.epoch||!state.current.alive){stream.getTracks().forEach(t=>t.stop());return;}
      media.current=stream;
      const ctx=new AudioContext({sampleRate:16000});context.current=ctx;await ctx.resume();
      await ctx.audioWorklet.addModule(`${import.meta.env.BASE_URL}audio/pcm-capture.js`);
      if(epoch!==state.current.epoch)return;
      const capture=new AudioWorkletNode(ctx,'pcm-capture');worklet.current=capture;
      ctx.createMediaStreamSource(stream).connect(capture);capture.connect(ctx.destination);
      const ws=new WebSocket(socketUrl(`/ws/v2/voice/${opts.current.id}`));socket.current=ws;
      capture.port.onmessage=({data}:{data:{pcm:ArrayBuffer;level:number}})=>{
        if(epoch!==state.current.epoch||!state.current.active)return;
        setLevel(state.current.muted?0:Math.min(1,data.level*12));
        if(ws.readyState!==WebSocket.OPEN)return;
        if(ws.bufferedAmount>128000){opts.current.onError(new Error('Voice network is too slow. Restart voice when your connection recovers.'));end();return;}
        // Silence keeps the provider connection alive while mute disables the physical audio track.
        ws.send(state.current.muted?new ArrayBuffer(data.pcm.byteLength):data.pcm);
      };
      timer.current=setTimeout(()=>{if(epoch===state.current.epoch&&!state.current.active){opts.current.onError(new Error('Realtime voice could not connect. Please try again.'));end();}},15000);
      ws.onmessage=message=>{
        if(epoch!==state.current.epoch)return;
        try{
          const data=voiceMessage.parse(JSON.parse(message.data));
          if(data.type==='ready'){
            clearTimeout(timer.current);state.current.active=true;state.current.starting=false;setActive(true);idle();
            if(opening)send({type:'replay',seq:opening.seq});
          }else if(data.type==='interrupt'){
            if(data.revision<state.current.revision)return;
            state.current.revision=data.revision;stopAudio();idle();
          }else if(data.type==='partial'){
            setPartial(data.text);if(data.text)idle();
          }else if(data.type==='committed'){
            setPartial('');void opts.current.onEvents();
          }else if(data.type==='reply'){
            void opts.current.onEvents();void playReply(data.event as Event,data.revision,epoch);
          }else if(data.type==='state'){
            if(data.revision<state.current.revision)return;
            if(data.state==='thinking')setStatus('thinking');else idle();
          }else if(data.type==='look'){
            if(data.revision===state.current.revision)setLookRequest(n=>n+1);
          }else if(data.type==='error'){
            opts.current.onError(new Error(data.message));if(data.fatal)end();else idle();
          }
        }catch{opts.current.onError(new Error('Invalid voice message. Please restart voice.'));end();}
      };
      ws.onclose=()=>{if(epoch!==state.current.epoch)return;opts.current.onError(new Error('Voice disconnected. Restart voice to reconnect; your saved turns are still here.'));end();};
      ws.onerror=()=>{if(epoch===state.current.epoch){opts.current.onError(new Error('Voice connection failed. Please restart voice.'));end();}};
    }catch(e){if(epoch===state.current.epoch){end();opts.current.onError(e);}}
  };
  const toggleMute=()=>{
    state.current.muted=!state.current.muted;setMuted(state.current.muted);setPartial('');
    media.current?.getAudioTracks().forEach(t=>{t.enabled=!state.current.muted;});
    send({type:'mute',muted:state.current.muted});if(!audio.current)idle();
  };
  const interrupt=()=>{stopAudio();send({type:'interrupt'});idle();};
  const sendNow=()=>send({type:'commit'});
  const sendText=(text:string)=>{stopAudio();send({type:'text',text});setPartial('');setStatus('thinking');};
  const acknowledge=async(event:Event)=>{
    const r=await fetch(`${API}/api/v2/sessions/${opts.current.id}/reply-complete`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({seq:event.seq})});
    if(!r.ok)throw new Error('Could not advance this step. Your conversation is saved.');
    const data=await r.json();if(data.action==='look')setLookRequest(n=>n+1);await opts.current.onEvents();
  };
  const runText=async(work:()=>Promise<Model<'TurnResult'>>)=>{
    stopAudio();setStatus('thinking');opts.current.onError(null);
    const epoch=++state.current.epoch;
    try{
      const result=await work();await opts.current.onEvents();if(epoch!==state.current.epoch)return;
      const reply=result.events.filter(e=>e.actor==='interviewer').at(-1);
      if(reply){const done=await say(reply);if(done&&epoch===state.current.epoch)await acknowledge(reply);}
    }catch(e){if(epoch===state.current.epoch)opts.current.onError(e);}
    finally{if(epoch===state.current.epoch)idle();}
  };
  const replay=async(event:Event,force=true)=>{
    if(state.current.active){
      replayWaiter.current?.resolve(false);
      return new Promise<boolean>(resolve=>{replayWaiter.current={seq:event.seq,resolve};send({type:'replay',seq:event.seq});});
    }
    try{return await say(event,force);}catch(e){opts.current.onError(e);return false;}finally{idle();}
  };
  useEffect(()=>{state.current.alive=true;return()=>{state.current.alive=false;end();};},[options.id]);
  useEffect(()=>{if(!options.sound){stopAudio();send({type:'interrupt'});idle();}},[options.sound]);
  useEffect(()=>{if(options.step>=3)end();},[options.step]);
  return {phase,active,muted,level,partial,lookRequest,start,end,toggleMute,interrupt,sendNow,sendText,runText,replay,noteTranscript:()=>{},busy:['connecting','thinking','speaking'].includes(phase)};
}
