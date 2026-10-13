import { useEffect, useRef, useState } from 'react';
import { api, apiFetch, openSessionSocket, type Event, type Model } from '../api/client';
import { voiceMessage } from './voiceProtocol';
import { acquireSpeech, releaseSpeech, type LocalSpeech, type LoadProgress } from './localSpeech';
import { LocalUtterance } from './localUtterance';
import { z } from 'zod';
import { wavPcm, connectionRequest, type SpeechOptions } from './connections';

export type VoicePhase='off'|'connecting'|'loading'|'listening'|'transcribing'|'thinking'|'speaking'|'muted';
type Options={id:string;step:number;endStep?:number;demo:boolean;sound:boolean;speech?:SpeechOptions;onEvents:()=>Promise<unknown>;onError:(e:unknown)=>void};

export function useVoiceConversation(options:Options) {
  const opts=useRef(options);opts.current=options;
  const [phase,setPhase]=useState<VoicePhase>('off'),[active,setActive]=useState(false),[muted,setMuted]=useState(false),[level,setLevel]=useState(0);
  const [partial,setPartial]=useState(''),[lookRequest,setLookRequest]=useState(0);
  const [speechNote,setSpeechNote]=useState(''),[loadProgress,setLoadProgress]=useState<LoadProgress|null>(null);
  const local=useRef({mode:'cloud',ttsQuota:false,tag:0,busy:false,pending:null as null|Float32Array});
  const stt=useRef<LocalSpeech|null>(null),tts=useRef<LocalSpeech|null>(null),gate=useRef<LocalUtterance|null>(null);
  const clipEpoch=useRef(0),clipUrl=useRef<string|null>(null),clipRequest=useRef<AbortController|null>(null);
  const note=(message:string)=>{if(state.current.alive)setSpeechNote(message);};
  const track=(p:LoadProgress|null)=>{if(state.current.alive)setLoadProgress(p);};
  const state=useRef({alive:true,active:false,muted:false,epoch:0,revision:0,starting:false});
  const socket=useRef<WebSocket|null>(null),media=useRef<MediaStream|null>(null),context=useRef<AudioContext|null>(null),worklet=useRef<AudioWorkletNode|null>(null);
  const audio=useRef<HTMLAudioElement|null>(null),finish=useRef<((completed:boolean)=>void)|null>(null);
  const replayWaiter=useRef<{seq:number;resolve:(completed:boolean)=>void}|null>(null);
  const timer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
  const setStatus=(p:VoicePhase)=>{if(state.current.alive)setPhase(p);};
  const idle=()=>setStatus(state.current.active?(state.current.muted?'muted':'listening'):'off');
  const send=(message:Record<string,unknown>)=>{if(socket.current?.readyState===WebSocket.OPEN)socket.current.send(JSON.stringify(message));};
  const stopAudio=()=>{
    clipEpoch.current++;clipRequest.current?.abort();clipRequest.current=null;
    if(clipUrl.current){URL.revokeObjectURL(clipUrl.current);clipUrl.current=null;}
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
    local.current.tag++;local.current.mode='cloud';local.current.pending=null;local.current.busy=false;
    gate.current?.reset();gate.current=null;releaseSpeech(stt.current);stt.current=null;releaseSpeech(tts.current);tts.current=null;
    state.current.muted=false;
    if(state.current.alive){setActive(false);setMuted(false);setLevel(0);setPartial('');setSpeechNote('');setLoadProgress(null);setStatus('off');}
  };
  const say=async(event:Event,force=false):Promise<boolean>=>{
    stopAudio();
    if(!opts.current.sound&&!force)return true;
    setStatus('speaking');
    const stamp=clipEpoch.current;
    return new Promise<boolean>((resolve,reject)=>{
      const complete=()=>{finish.current=null;audio.current=null;if(clipUrl.current){URL.revokeObjectURL(clipUrl.current);clipUrl.current=null;}resolve(true);};
      finish.current=resolve;
      if(opts.current.demo||opts.current.speech?.tts==='browser'){
        const u=new SpeechSynthesisUtterance(String(event.payload.text));u.onend=complete;u.onerror=()=>{finish.current=null;resolve(false);};speechSynthesis.speak(u);
      }else{
        void (async()=>{
          let blob:Blob|undefined;
          if(!local.current.ttsQuota){
            const controller=new AbortController();clipRequest.current=controller;
            const response=await apiFetch(`/sessions/${opts.current.id}/speech/${event.seq}`,{signal:controller.signal});
            if(response.headers.get('X-PrepCrew-Speech-Fallback')==='browser'){
              if(stamp!==clipEpoch.current)return;
              note('Using your browser’s voice. Live microphone conversations need optional ElevenLabs settings.');
              if(!window.speechSynthesis){complete();return;}
              const utterance=new SpeechSynthesisUtterance(String(event.payload.text));
              utterance.onend=complete;
              // Playback is optional: a missing system voice must not prevent
              // a saved typed answer from advancing to the next step.
              utterance.onerror=complete;
              window.speechSynthesis.speak(utterance);return;
            }
            if(['quota','local'].includes(response.headers.get('X-PrepCrew-Speech-Fallback')||''))local.current.ttsQuota=true;
            else if(!response.ok)throw new Error('Dana’s voice is unavailable. The transcript is saved; use Replay to try again.');
            else blob=await response.blob();
          }
          if(stamp!==clipEpoch.current)return;
          if(!blob){
            setStatus('loading');
            note('Starting Dana’s Kokoro voice on your GPU; first use downloads model files.');
            if(!tts.current){
              const speech=acquireSpeech('tts',track);tts.current=speech;
              try{await speech.load();}
              catch(e){speech.close();if(tts.current===speech)tts.current=null;throw e;}
              finally{if(stamp===clipEpoch.current)track(null);}
            }
            if(stamp!==clipEpoch.current)return;
            const output=await tts.current.infer(opts.current.id,{seq:event.seq,voice:opts.current.speech?.kokoro_voice||'af_heart'});
            if(!output.wav)throw new Error('Kokoro returned no audio.');
            blob=new Blob([output.wav],{type:'audio/wav'});note('Dana’s voice: Kokoro · local WebGPU');
          }
          if(stamp!==clipEpoch.current)return;
          setStatus('speaking');
          const url=URL.createObjectURL(blob);clipUrl.current=url;
          const clip=new Audio(url);audio.current=clip;
          const failed=()=>{if(stamp!==clipEpoch.current)return;finish.current=null;stopAudio();reject(new Error('Dana’s audio could not play. The transcript is saved; use Replay to try again.'));};
          clip.onended=complete;clip.onerror=failed;await clip.play().catch(failed);
        })().catch(e=>{if(stamp===clipEpoch.current){finish.current=null;reject(e);}});
      }
    });
  };
  const recognize=async(pcm:Float32Array,final:boolean,epoch:number)=>{
    if(local.current.mode==='segment'&&!final){stopAudio();send({type:'interrupt'});idle();return;}
    if(local.current.busy){
      if(final){
        if(local.current.pending){opts.current.onError(new Error('Local transcription cannot keep up. Your saved turns are safe; continue by typing.'));end();return;}
        local.current.pending=pcm;
      }
      return;
    }
    const tag=local.current.tag;local.current.busy=true;
    try{
      const output=local.current.mode==='segment'
        ?z.object({text:z.string(),inference_id:z.string()}).parse(await connectionRequest(`/sessions/${opts.current.id}/transcriptions`,{method:'POST',headers:{'Content-Type':'audio/wav'},body:wavPcm(pcm)}))
        :await stt.current!.infer(opts.current.id,{pcm});
      if(epoch!==state.current.epoch||tag!==local.current.tag||state.current.muted)return;
      send({type:final?'local_final':'local_partial',text:output.text||'',inference_id:output.inference_id});
    }catch(e){if(epoch===state.current.epoch){opts.current.onError(e);end();}}
    finally{
      if(epoch===state.current.epoch){
        local.current.busy=false;const pending=local.current.pending;local.current.pending=null;
        if(pending)void recognize(pending,true,epoch);
      }
    }
  };
  const startLocal=async(epoch:number,opening?:Event,provider='parakeet')=>{
    if(local.current.mode!=='cloud')return;
    setPartial('');
    clearTimeout(timer.current);local.current.mode='loading';
    // Keep Stop/Mute available during downloads, including quota before handshake.
    state.current.active=true;state.current.starting=false;setActive(true);setStatus('loading');
    note(provider==='openai'?'Microphone: OpenAI speech · continuous capture with utterance transcription.':'Starting Parakeet on your GPU. First use downloads model files; speak after Listening appears.');
    opts.current.onError(null);
    try{
      if(provider==='parakeet'){
        const mode=opts.current.speech?.parakeet||'balanced';
        stt.current=acquireSpeech('stt',track,mode);try{await stt.current.load({parakeet:mode});}finally{if(epoch===state.current.epoch)track(null);}
      }
      if(epoch!==state.current.epoch)return;
      gate.current=new LocalUtterance((pcm,final)=>void recognize(pcm,final,epoch));local.current.mode=provider==='openai'?'segment':'local';
      note(provider==='openai'?'Microphone: OpenAI speech · live capture':'Microphone: Parakeet · local WebGPU encoder / INT8 WASM decoder');idle();
      if(opening)send({type:'replay',seq:opening.seq});
    }catch(e){if(epoch===state.current.epoch){opts.current.onError(e);end();}}
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
      const ws=await openSessionSocket(`/ws/v2/voice/${opts.current.id}`,opts.current.id,'voice');
      if(epoch!==state.current.epoch||!state.current.alive){ws.close();return;}
      socket.current=ws;
      capture.port.onmessage=({data}:{data:{pcm:ArrayBuffer;level:number}})=>{
        if(epoch!==state.current.epoch||!state.current.active)return;
        setLevel(state.current.muted?0:Math.min(1,data.level*12));
        if(local.current.mode!=='cloud'){
          if(['local','segment'].includes(local.current.mode)&&!state.current.muted)gate.current?.push(data.pcm,data.level);
          return;
        }
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
          if(data.type==='fallback'){
            const initial=!state.current.active;void startLocal(epoch,initial?opening:undefined,data.provider);
          }else if(data.type==='ready'){
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
    local.current.tag++;local.current.pending=null;gate.current?.reset();
    media.current?.getAudioTracks().forEach(t=>{t.enabled=!state.current.muted;});
    send({type:'mute',muted:state.current.muted});if(!audio.current)idle();
  };
  const interrupt=()=>{stopAudio();send({type:'interrupt'});idle();};
  const sendNow=()=>{if(['local','segment'].includes(local.current.mode))gate.current?.commit();else send({type:'commit'});};
  const sendText=(text:string)=>{stopAudio();local.current.tag++;local.current.pending=null;gate.current?.reset();send({type:'text',text});setPartial('');setStatus('thinking');};
  const acknowledge=async(event:Event)=>{
    const r=await apiFetch(`/sessions/${opts.current.id}/reply-complete`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({seq:event.seq})});
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
  useEffect(()=>{if(options.step>=(options.endStep??3))end();},[options.step,options.endStep]);
  useEffect(()=>{local.current.tag++;local.current.pending=null;gate.current?.reset();setPartial('');},[options.step]);
  return {phase,active,muted,level,partial,lookRequest,speechNote,loadProgress,start,end,toggleMute,interrupt,sendNow,sendText,runText,replay,noteTranscript:()=>{},busy:['connecting','loading','thinking','speaking'].includes(phase)};
}
