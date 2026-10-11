// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useVoiceConversation } from './useVoiceConversation';
const localMocks=vi.hoisted(()=>({all:[] as {kind:string;load:ReturnType<typeof vi.fn>;infer:ReturnType<typeof vi.fn>;close:ReturnType<typeof vi.fn>;released:boolean}[]}));
vi.mock('./localSpeech',()=>{
 class LocalSpeech {
  kind:string;load=vi.fn(async()=>{});infer=vi.fn(async()=>({text:'Can we support bursts?',inference_id:'local-job',wav:new ArrayBuffer(44)}));close=vi.fn();released=false;
  constructor(kind:string){this.kind=kind;localMocks.all.push(this);}
 }
 return {LocalSpeech,acquireSpeech:(kind:string)=>new LocalSpeech(kind),releaseSpeech:(speech:LocalSpeech|null)=>{if(speech)speech.released=true;}};
});

const track={stop:vi.fn(),enabled:true};
class FakeSocket {
 static OPEN=1;static all:FakeSocket[]=[];readyState=1;bufferedAmount=0;sent:unknown[]=[];
 onmessage:((e:{data:string})=>void)|null=null;onclose:(()=>void)|null=null;onerror:(()=>void)|null=null;
 constructor(){FakeSocket.all.push(this);}send(data:unknown){this.sent.push(data);}close(){this.readyState=3;}
 receive(message:unknown){this.onmessage?.({data:JSON.stringify(message)});}
}
class FakeWorklet {
 static all:FakeWorklet[]=[];port:{onmessage:((e:{data:{pcm:ArrayBuffer;level:number}})=>void)|null}={onmessage:null};
 constructor(){FakeWorklet.all.push(this);}connect(){}disconnect(){}
 frame(){this.port.onmessage?.({data:{pcm:new ArrayBuffer(3200),level:.04}});}
}
class FakeAudio {
 static all:FakeAudio[]=[];onended:(()=>void)|null=null;onerror:(()=>void)|null=null;
 pause=vi.fn();load=vi.fn();removeAttribute=vi.fn();
 constructor(){FakeAudio.all.push(this);}play(){return Promise.resolve();}
}
const options=()=>({id:'session',step:0,demo:false,sound:true,onEvents:vi.fn(async()=>{}),onError:vi.fn()});
const reply={session_id:'session',seq:2,kind:'turn',actor:'interviewer',step:0,ts:new Date().toISOString(),payload:{text:'What about bursts?'}};
const messages=(ws:FakeSocket)=>ws.sent.filter(x=>typeof x==='string').map(x=>JSON.parse(x as string));

beforeEach(()=>{
 vi.useFakeTimers();FakeSocket.all=[];FakeWorklet.all=[];FakeAudio.all=[];track.stop.mockClear();track.enabled=true;
 localMocks.all=[];
 vi.stubGlobal('fetch',vi.fn(async()=>({ok:true,status:200,headers:new Headers(),blob:async()=>new Blob(['synthetic audio'])})));
 URL.createObjectURL=vi.fn(()=> 'blob:synthetic');URL.revokeObjectURL=vi.fn();
 vi.stubGlobal('WebSocket',FakeSocket);vi.stubGlobal('Audio',FakeAudio);vi.stubGlobal('AudioWorkletNode',FakeWorklet);
 vi.stubGlobal('AudioContext',class {
  destination={};audioWorklet={addModule:vi.fn(async()=>{})};
  resume(){return Promise.resolve();}close(){return Promise.resolve();}
  createMediaStreamSource(){return {connect:vi.fn()};}
 });
 Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia:vi.fn(async()=>({getTracks:()=>[track],getAudioTracks:()=>[track]}))}});
});
afterEach(()=>{cleanup();vi.useRealTimers();vi.unstubAllGlobals();});

async function start(){
 const opts=options();const hook=renderHook(()=>useVoiceConversation(opts));
 await act(async()=>{await hook.result.current.start();});
 const ws=FakeSocket.all[0];act(()=>ws.receive({type:'ready',revision:0}));
 return {...hook,ws,opts,capture:FakeWorklet.all[0]};
}

describe('full duplex voice lifecycle',()=>{
 it('switches quota to local STT on the same socket without sending more microphone audio upstream',async()=>{
  const {result,ws,capture}=await start();act(()=>capture.frame());const sent=ws.sent.filter(x=>x instanceof ArrayBuffer).length;
  await act(async()=>ws.receive({type:'fallback',provider:'parakeet',reason:'quota'}));
  expect(result.current.active).toBe(true);expect(result.current.speechNote).toContain('Parakeet');expect(result.current.loadProgress).toBeNull();
  await act(async()=>{for(let n=0;n<12;n++)capture.frame();});
  expect(ws.sent.filter(x=>x instanceof ArrayBuffer)).toHaveLength(sent);
  expect(messages(ws)).toContainEqual({type:'local_partial',text:'Can we support bursts?',inference_id:'local-job'});
  await act(async()=>result.current.sendNow());
  expect(messages(ws)).toContainEqual({type:'local_final',text:'Can we support bursts?',inference_id:'local-job'});
  act(()=>result.current.end());expect(localMocks.all[0].released).toBe(true);expect(localMocks.all[0].close).not.toHaveBeenCalled();expect(track.stop).toHaveBeenCalled();
 });
 it('handles quota before ready and replays the opening only after local recognition loads',async()=>{
  const hook=renderHook(()=>useVoiceConversation(options()));await act(async()=>hook.result.current.start(reply));const ws=FakeSocket.all[0];
  await act(async()=>ws.receive({type:'fallback',provider:'parakeet',reason:'quota'}));
  expect(hook.result.current.active).toBe(true);expect(messages(ws)).toContainEqual({type:'replay',seq:2});
  act(()=>vi.advanceTimersByTime(16000));expect(hook.result.current.active).toBe(true);
 });
 it('uses Kokoro only for explicit quota and keeps it for subsequent replies',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>new Response('',{status:503,headers:{'X-PrepCrew-Speech-Fallback':'quota'}})));
  const {ws}=await start();await act(async()=>ws.receive({type:'reply',event:reply,revision:1}));
  expect(localMocks.all[0].kind).toBe('tts');expect(localMocks.all[0].infer).toHaveBeenCalledWith('session',{seq:2});
  expect(messages(ws).some(m=>m.type==='playback_done')).toBe(false);
  await act(async()=>FakeAudio.all[0].onended?.());
  expect(messages(ws)).toContainEqual({type:'playback_done',seq:2,revision:1});
  await act(async()=>ws.receive({type:'reply',event:{...reply,seq:3},revision:2}));expect(fetch).toHaveBeenCalledTimes(1);
 });
 it('does not conceal authentication or provider failures by loading local models',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>new Response('',{status:503})));
  const {ws,opts}=await start();await act(async()=>ws.receive({type:'reply',event:reply,revision:1}));
  expect(localMocks.all).toHaveLength(0);expect(opts.onError).toHaveBeenCalledWith(expect.objectContaining({message:expect.stringContaining('unavailable')}));
 });
 it('discards local results recognized across mute and never sends them as evidence',async()=>{
  const {result,ws,capture}=await start();await act(async()=>ws.receive({type:'fallback',provider:'parakeet',reason:'quota'}));
  let resolve!:(v:unknown)=>void;localMocks.all[0].infer.mockImplementationOnce(()=>new Promise(r=>resolve=r));
  act(()=>{for(let n=0;n<12;n++)capture.frame();});act(()=>result.current.toggleMute());
  await act(async()=>resolve({text:'Old speech',inference_id:'old-job'}));
  expect(messages(ws).some(m=>m.type==='local_partial'||m.type==='local_final')).toBe(false);
 });
 it('streams microphone frames while Dana is speaking, and cancels audio on barge-in',async()=>{
  const {result,ws,capture}=await start();
  await act(async()=>ws.receive({type:'reply',event:reply,revision:1}));
  expect(result.current.phase).toBe('speaking');
  act(()=>capture.frame());expect(ws.sent.some(x=>x instanceof ArrayBuffer)).toBe(true);
  await act(async()=>{ws.receive({type:'interrupt',revision:2});ws.receive({type:'partial',text:'Wait, let me explain'});});
  expect(FakeAudio.all[0].pause).toHaveBeenCalled();expect(FakeAudio.all[0].load).toHaveBeenCalled();
  expect(result.current.partial).toBe('Wait, let me explain');
  expect(messages(ws).some(x=>x.type==='playback_done')).toBe(false);
  expect(track.stop).not.toHaveBeenCalled();
 });
 it('ignores a stale reply arriving after interruption',async()=>{
  const {ws}=await start();
  act(()=>ws.receive({type:'interrupt',revision:4}));
  await act(async()=>ws.receive({type:'reply',event:reply,revision:3}));
  expect(FakeAudio.all).toHaveLength(0);
 });
 it('only acknowledges completed playback for progression',async()=>{
  const {ws}=await start();
  await act(async()=>ws.receive({type:'reply',event:reply,revision:1}));
  expect(messages(ws).some(x=>x.type==='playback_done')).toBe(false);
  await act(async()=>FakeAudio.all[0].onended?.());
  expect(messages(ws)).toContainEqual({type:'playback_done',seq:2,revision:1});
 });
 it('mute disables the physical track but keeps a silence stream alive',async()=>{
  const {result,ws,capture}=await start();act(()=>result.current.toggleMute());
  expect(track.enabled).toBe(false);expect(result.current.muted).toBe(true);
  act(()=>capture.frame());expect(ws.sent.at(-1)).toBeInstanceOf(ArrayBuffer);
  expect([...new Uint8Array(ws.sent.at(-1) as ArrayBuffer)].every(x=>x===0)).toBe(true);
  act(()=>result.current.toggleMute());expect(track.enabled).toBe(true);
 });
 it('allows typed interruption while a spoken response is playing',async()=>{
  const {result,ws}=await start();
  await act(async()=>ws.receive({type:'reply',event:reply,revision:1}));
  act(()=>result.current.sendText('Actually, I meant per user.'));
  expect(FakeAudio.all[0].pause).toHaveBeenCalled();
  expect(messages(ws)).toContainEqual({type:'text',text:'Actually, I meant per user.'});
 });
 it('releases the microphone and stops audio when the socket fails',async()=>{
  const {result,ws,opts}=await start();
  act(()=>ws.receive({type:'error',fatal:true,message:'Provider quota reached'}));
  expect(track.stop).toHaveBeenCalled();expect(result.current.active).toBe(false);
  expect(opts.onError).toHaveBeenCalledWith(expect.objectContaining({message:'Provider quota reached'}));
 });
 it('does not start a socket after microphone permission resolves following unmount',async()=>{
  let grant!:(stream:unknown)=>void;
  vi.mocked(navigator.mediaDevices.getUserMedia).mockImplementation(()=>new Promise(resolve=>{grant=resolve as (s:unknown)=>void;}));
  const {result,unmount}=renderHook(()=>useVoiceConversation(options()));
  let pending:Promise<void>;act(()=>{pending=result.current.start();});unmount();
  await act(async()=>{grant({getTracks:()=>[track],getAudioTracks:()=>[track]});await pending;});
  expect(track.stop).toHaveBeenCalled();expect(FakeSocket.all).toHaveLength(0);
 });
});
