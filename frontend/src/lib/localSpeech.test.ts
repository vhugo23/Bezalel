// @vitest-environment jsdom
import { afterEach,beforeEach,it,expect,vi } from 'vitest';
import { LocalSpeech, acquireSpeech, releaseSpeech } from './localSpeech';
class FakeWorker {
 static all:FakeWorker[]=[];onmessage:((event:{data:unknown})=>void)|null=null;onerror:(()=>void)|null=null;
 sent:Record<string,unknown>[]=[];terminate=vi.fn();
 constructor(){FakeWorker.all.push(this);}
 postMessage(data:Record<string,unknown>){this.sent.push(data);}
 reply(data:unknown){this.onmessage?.({data});}
}
beforeEach(()=>{
 FakeWorker.all=[];vi.stubGlobal('Worker',FakeWorker);
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({id:'audit-id',text:'Saved Dana words'}),{status:200})));
});
afterEach(()=>vi.unstubAllGlobals());
it('creates an audit before inference and synthesizes only server-saved text',async()=>{
 const speech=new LocalSpeech('tts',()=>{});const worker=FakeWorker.all[0];
 const operation=speech.infer('s',{seq:7,text:'Forged client text'});
 await vi.waitFor(()=>expect(worker.sent).toHaveLength(1));
 expect(worker.sent[0].text).toBe('Saved Dana words');
 const wav=new ArrayBuffer(44);worker.reply({id:1,wav});expect((await operation).wav).toBe(wav);
 const calls=vi.mocked(fetch).mock.calls;
 expect(JSON.parse(String(calls[0][1]?.body))).toEqual({kind:'tts',seq:7});
 expect(JSON.parse(String(calls[1][1]?.body))).toMatchObject({status:'succeeded',text:''});speech.close();
});
it('does not run inference when its audit cannot be created',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response('',{status:503})));
 const speech=new LocalSpeech('stt',()=>{});
 await expect(speech.infer('s',{pcm:new Float32Array(1600)})).rejects.toThrow('audit');
 expect(FakeWorker.all[0].sent).toHaveLength(0);speech.close();
});
it('closes and audits a cancelled inference instead of publishing a late transcript',async()=>{
 const speech=new LocalSpeech('stt',()=>{});const worker=FakeWorker.all[0];
 const operation=speech.infer('s',{pcm:new Float32Array(1600)});const rejected=expect(operation).rejects.toThrow('stopped');
 await vi.waitFor(()=>expect(worker.sent).toHaveLength(1));speech.close();await rejected;
 worker.reply({id:1,text:'Late words'});
 const calls=vi.mocked(fetch).mock.calls;expect(JSON.parse(String(calls[1][1]?.body))).toMatchObject({status:'failed',text:''});
 expect(worker.terminate).toHaveBeenCalled();
});
it('forwards aggregated model progress and ignores malformed progress',()=>{
 const progress=vi.fn();const speech=new LocalSpeech('stt',progress);const worker=FakeWorker.all[0];
 worker.reply({type:'progress',model:'Parakeet',stage:'download',loaded:5e8,total:1e9,cached:false});
 worker.reply({type:'progress',message:'Downloading Parakeet: 3%'});
 expect(progress).toHaveBeenCalledTimes(1);
 expect(progress).toHaveBeenCalledWith({model:'Parakeet',stage:'download',loaded:5e8,total:1e9,cached:false});
 expect(worker.terminate).not.toHaveBeenCalled();speech.close();
});
it('keeps a loaded model worker across voice restarts and frees it after idling',async()=>{
 vi.useFakeTimers();
 try{
  const first=acquireSpeech('tts',()=>{});const loading=first.load();
  FakeWorker.all[0].reply({id:1,ready:true});await loading;releaseSpeech(first);
  const progress=vi.fn(),again=acquireSpeech('tts',progress);
  expect(again).toBe(first);expect(FakeWorker.all).toHaveLength(1);
  FakeWorker.all[0].reply({type:'progress',model:'Kokoro',stage:'download',loaded:1,total:2,cached:true});expect(progress).toHaveBeenCalled();
  releaseSpeech(again);vi.advanceTimersByTime(15*60_000);
  expect(FakeWorker.all[0].terminate).toHaveBeenCalled();
  expect(acquireSpeech('tts',()=>{})).not.toBe(first);
 }finally{vi.useRealTimers();}
});
it('terminates an unfinished model download immediately when voice stops',async()=>{
 const speech=acquireSpeech('stt',()=>{}),worker=FakeWorker.all[0];
 const loading=expect(speech.load()).rejects.toThrow('Continue by typing');
 releaseSpeech(speech);await loading;
 expect(worker.terminate).toHaveBeenCalled();expect(speech.closed).toBe(true);
});
it('discards a failed download so a restart can acquire a fresh worker',async()=>{
 const speech=acquireSpeech('stt',()=>{}),worker=FakeWorker.all[0];
 const loading=expect(speech.load()).rejects.toThrow('WebGPU');
 worker.reply({id:1,error:'WebGPU unavailable. Continue by typing.'});await loading;
 expect(worker.terminate).toHaveBeenCalled();
 const replacement=acquireSpeech('stt',()=>{});expect(replacement).not.toBe(speech);replacement.close();
});
