import { test, expect, chromium } from '@playwright/test';
import { writeFile } from 'node:fs/promises';

test('local speech audits are scoped, single-use and accept only saved Dana text',async({page,request})=>{
 await page.goto('/');
 const health=await (await request.get('/api/v2/health')).json();expect(health.test_environment).toBe(true);
 const session=await (await request.post('/api/v2/sessions',{data:{track_id:'e2e-two-step-track',consent:true}})).json();
 const path=`/api/v2/sessions/${session.id}/local-speech/jobs`;
 const tts=await (await request.post(path,{data:{kind:'tts',seq:session.events.find((e:{actor:string})=>e.actor==='interviewer').seq}})).json();
 expect(tts.text).toBeTruthy();
 expect((await request.post(path,{data:{kind:'tts',seq:999999}})).status()).toBe(404);
 const done={status:'succeeded',text:'Synthetic browser report',latency_ms:0};
 expect((await request.post(`${path}/${tts.id}`,{data:done})).status()).toBe(200);
 expect((await request.post(`${path}/${tts.id}`,{data:done})).status()).toBe(409);
 const other=await (await request.post('/api/v2/sessions',{data:{track_id:'e2e-two-step-track',consent:true}})).json();
 const job=await (await request.post(path,{data:{kind:'stt'}})).json();
 expect((await request.post(`/api/v2/sessions/${other.id}/local-speech/jobs/${job.id}`,{data:done})).status()).toBe(409);
 expect((await request.post(`${path}/${job.id}`,{data:done})).status()).toBe(200);
});

test('opt-in real WebGPU Kokoro to Parakeet roundtrip with audited synthetic speech',async()=>{
 test.skip(process.env.PREPCREW_LOCAL_GPU_SMOKE!=='1','Large real-model download; explicitly opt in. No paid API calls.');
 test.setTimeout(600000);
 const browser=await chromium.launchPersistentContext('../.artifacts/e2e-webgpu-profile',{channel:'chromium',headless:true,args:['--enable-unsafe-webgpu','--use-angle=d3d11']});
 try{
  const page=await browser.newPage();
  // This long model test uses HTTP only. Ignore dev HMR reloads from editor
  // saves/file watchers while compiling; the UI socket journey is separate.
  await page.routeWebSocket('**',()=>{});
  await page.goto(process.env.PREPCREW_E2E_ORIGIN!);
  // Diagnostics contain only this test's synthetic speech; never instrument a
  // real interview. Keep runtime failures out of the production UI/log path.
  page.on('console',message=>{if(message.text().startsWith('SYNTHETIC_LOCAL_SPEECH_DIAGNOSTIC'))console.log(message.text());});
  await page.route('**/src/lib/localSpeech.worker.ts*',async route=>{
   const response=await route.fetch();const body=(await response.text()).replace('catch {',"catch (error) {console.error('SYNTHETIC_LOCAL_SPEECH_DIAGNOSTIC',error);");
   const instrumented=body.replace('const result = await model.transcribe', `const join=model.joinerSession.run.bind(model.joinerSession);let logged=false;model.joinerSession.run=async(...args)=>{const outputs=await join(...args);if(!logged){logged=true;const v=outputs.outputs;const a=Array.from(v.data,Number);console.log('SYNTHETIC_LOCAL_SPEECH_DIAGNOSTIC',JSON.stringify({decoder:v.type,finite:a.filter(Number.isFinite).length,size:a.length,argmax:a.indexOf(Math.max(...a))}));}return outputs;};const run=model.encoderSession.run.bind(model.encoderSession);model.encoderSession.run=async(...args)=>{const data=Array.from(args[0].audio_signal.data,Number);console.log('SYNTHETIC_LOCAL_SPEECH_DIAGNOSTIC',JSON.stringify({inputFinite:data.filter(Number.isFinite).length,size:data.length,min:data.reduce((a,b)=>Math.min(a,b),Infinity),max:data.reduce((a,b)=>Math.max(a,b),-Infinity)}));const outputs=await run(...args);for(const [key,v] of Object.entries(outputs)){const values=Array.from(v.data,Number);console.log('SYNTHETIC_LOCAL_SPEECH_DIAGNOSTIC',JSON.stringify({key,type:v.type,dims:v.dims,finite:values.filter(Number.isFinite).length,size:values.length,min:values.reduce((a,b)=>Math.min(a,b),Infinity),max:values.reduce((a,b)=>Math.max(a,b),-Infinity)}));}return outputs;};const result = await model.transcribe`);
   await route.fulfill({response,body:instrumented});
  });
  const health=await (await page.request.get('/api/v2/health')).json();expect(health.test_environment).toBe(true);expect(health.demo).toBe(true);
  const session=await (await page.request.post('/api/v2/sessions',{data:{track_id:'e2e-two-step-track',consent:true}})).json();
  const seq=session.events.find((e:{actor:string})=>e.actor==='interviewer').seq;
  await page.exposeFunction('captureSynthetic',(bytes:number[])=>writeFile('../.artifacts/e2e/synthetic-kokoro.wav',Buffer.from(bytes)));
  await page.exposeFunction('localProgress',(progress:unknown)=>console.log(JSON.stringify(progress)));
  const output=await page.evaluate(async({sid,seq})=>{
   // Vite serves this source module only in the isolated acceptance dev server.
   const {LocalSpeech}=await import(/* @vite-ignore */ '/src/lib/localSpeech.ts');
   const progress=(p:unknown)=>(window as unknown as {localProgress:(p:unknown)=>void}).localProgress(p);
   const tts=new LocalSpeech('tts',progress),stt=new LocalSpeech('stt',progress);
   const context=new AudioContext({sampleRate:16000});
   try{
    await tts.load();const spoken=await tts.infer(sid,{seq});
    await (window as unknown as {captureSynthetic:(bytes:number[])=>Promise<void>}).captureSynthetic(Array.from(new Uint8Array(spoken.wav)));
    const decoded=await context.decodeAudioData(spoken.wav);
    const pcm=decoded.getChannelData(0);console.log('SYNTHETIC_LOCAL_SPEECH_DIAGNOSTIC',JSON.stringify({pcm:pcm.length,min:pcm.reduce((a,b)=>Math.min(a,b),Infinity),max:pcm.reduce((a,b)=>Math.max(a,b),-Infinity),mean:pcm.reduce((a,b)=>a+b,0)/pcm.length}));const energy=pcm.reduce((sum,n)=>sum+n*n,0)/pcm.length;if(!Number.isFinite(energy)||energy<1e-6)throw new Error('Synthetic Kokoro waveform is silent or invalid');
    await stt.load();const heard=await stt.infer(sid,{pcm:decoded.getChannelData(0)});
    if(!heard.text){const reference=await context.decodeAudioData(await (await fetch('https://huggingface.co/datasets/Xenova/transformers.js-docs/resolve/main/jfk.wav')).arrayBuffer());const checked=await stt.infer(sid,{pcm:reference.getChannelData(0)});console.log('SYNTHETIC_LOCAL_SPEECH_DIAGNOSTIC',JSON.stringify({publicReferenceTextLength:checked.text?.length}));}
    return {text:heard.text,rate:decoded.sampleRate};
   }finally{tts.close();stt.close();await context.close();}
  },{sid:session.id,seq});
  expect(output.rate).toBe(16000);expect(output.text.length).toBeGreaterThan(10);
  const expectedWords=new Set<string>(session.events.find((e:{seq:number})=>e.seq===seq).payload.text.toLowerCase().match(/[a-z]+/g));
  const heardWords=new Set<string>(output.text.toLowerCase().match(/[a-z]+/g));
  expect([...expectedWords].filter(w=>heardWords.has(w)).length/expectedWords.size).toBeGreaterThanOrEqual(.7);
  console.log('Real synthetic local speech roundtrip passed; transcript omitted.');
 }finally{await browser.close();}
});
