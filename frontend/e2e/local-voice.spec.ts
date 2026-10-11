import { test,expect,chromium } from '@playwright/test';

test('quota fallback remains usable with model downloads, local audio and Stop controls',async()=>{
 const browser=await chromium.launch({args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--autoplay-policy=no-user-gesture-required']});
 try{
  const context=await browser.newContext({baseURL:process.env.PREPCREW_E2E_ORIGIN,permissions:['microphone']});const page=await context.newPage();
  const health=await (await page.request.get('/api/v2/health')).json();expect(health.test_environment).toBe(true);
  const session=await (await page.request.post('/api/v2/sessions',{data:{track_id:'e2e-two-step-track',consent:true}})).json();
  const opening=session.events.find((e:{actor:string})=>e.actor==='interviewer');
  await page.addInitScript(()=>{
   const NativeWorker=window.Worker;
   window.Worker=class extends EventTarget {
    onmessage:((event:MessageEvent)=>void)|null=null;
    constructor(url:string|URL,options?:WorkerOptions){super();if(!String(url).includes('localSpeech.worker'))return new NativeWorker(url,options) as unknown as Worker;}
    postMessage(data:{id:number;load?:boolean;kind:string}){
     if(data.load)setTimeout(()=>this.onmessage?.(new MessageEvent('message',{data:{type:'progress',model:data.kind==='stt'?'Parakeet':'Kokoro',stage:'download',loaded:5e8,total:1e9,cached:false}})),10);
     const wav=new ArrayBuffer(3244),v=new DataView(wav);
     const text=(offset:number,s:string)=>{for(let i=0;i<s.length;i++)v.setUint8(offset+i,s.charCodeAt(i));};
     text(0,'RIFF');v.setUint32(4,3236,true);text(8,'WAVE');text(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,16000,true);v.setUint32(28,32000,true);v.setUint16(32,2,true);v.setUint16(34,16,true);text(36,'data');v.setUint32(40,3200,true);
     setTimeout(()=>this.onmessage?.(new MessageEvent('message',{data:{id:data.id,...(data.load?{ready:true}:data.kind==='tts'?{wav}:{text:'Synthetic local speech'})}})),data.load?1500:20);
    }
    terminate(){}
   } as unknown as typeof Worker;
  });
  await page.route(`**/api/v2/sessions/${session.id}`,async route=>{const response=await route.fetch();await route.fulfill({response,json:{...await response.json(),demo:false}});});
  await page.route(`**/api/v2/sessions/${session.id}/speech/*`,route=>route.fulfill({status:503,headers:{'X-PrepCrew-Speech-Fallback':'quota'},json:{detail:'Synthetic quota'}}));
  await page.routeWebSocket(`**/ws/v2/voice/${session.id}`,ws=>{
   ws.onMessage(raw=>{if(typeof raw!=='string')return;const m=JSON.parse(raw);if(m.type==='replay')ws.send(JSON.stringify({type:'reply',event:opening,revision:1}));});
   ws.send(JSON.stringify({type:'fallback',provider:'parakeet',reason:'quota'}));
  });
  await page.goto(`/session/${session.id}`);await page.getByRole('button',{name:'Start voice',exact:true}).click();
  await expect(page.getByRole('button',{name:'End voice',exact:true})).toBeVisible();
  await expect(page.getByRole('progressbar',{name:'Parakeet model'})).toHaveAttribute('aria-valuenow','50');
  await expect(page.locator('.voice-presence')).toHaveAttribute('title','Dana’s voice: Kokoro · local WebGPU');
  await page.getByRole('button',{name:'Mute microphone'}).click();await expect(page.getByRole('button',{name:'Unmute microphone'})).toBeVisible();
  await page.getByRole('button',{name:'End voice',exact:true}).click();await expect(page.getByRole('button',{name:'Start voice',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'Start voice',exact:true}).click();
  await expect(page.getByRole('progressbar',{name:'Parakeet model'})).toBeVisible();
  await page.getByRole('button',{name:'End voice',exact:true}).click();
  await expect(page.getByRole('progressbar')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Start voice',exact:true})).toBeEnabled();
  await page.screenshot({path:'../.artifacts/e2e/local-voice.png',fullPage:true});
 }finally{await browser.close();}
});
