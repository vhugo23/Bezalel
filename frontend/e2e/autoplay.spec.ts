import { test, expect, type APIRequestContext, type Page } from '@playwright/test';

// Real disposable HTTP/database/board/grading journey; only device speech is accelerated.
async function speech(page:Page,hold=false){
 await page.route('**/demo/speech/*',route=>route.fulfill({status:503,body:'Synthetic browser speech fallback'}));
 await page.addInitScript(({hold})=>{
  Object.defineProperty(window,'speechSynthesis',{configurable:true,value:{
   getVoices:()=>[],cancel:()=>{},speak:(utterance:SpeechSynthesisUtterance)=>{
    if(!hold)setTimeout(()=>utterance.onend?.(new Event('end') as SpeechSynthesisEvent),50);
   },speaking:false,pending:false,paused:false,addEventListener:()=>{},removeEventListener:()=>{},
  }});
 },{hold});
}
async function start(request:APIRequestContext,trackTitle:string){
 const health=await (await request.get('/api/v2/health')).json();
 expect(health.test_environment).toBe(true);expect(health.demo).toBe(true);
 const response=await request.post('/api/v2/plans',{data:{user_id:'e2e-autoplay-user',name:'Synthetic autoplay candidate',role:'Software engineer',companies:[],struggles:['System design','Linux diagnostics'],question:'Design a public API rate limiter.'}});
 expect(response.ok()).toBe(true);const plan=await response.json();
 const track=plan.tracks.find((t:{title:string})=>t.title===trackTitle);expect(track.ready).toBe(true);
 const result=await request.post('/api/v2/sessions',{data:{track_id:track.id,consent:true}});
 expect(result.ok()).toBe(true);return result.json();
}
for(const [title,mistake] of [
 ['System design: whiteboard','separate GET followed by SET'],
 ['Fix the site on the Pi','644 gives every user write permission'],
])test(`autoplay ${title} saves authored interaction and an explicitly scripted recap`,async({page,request})=>{
 test.setTimeout(240000);
 await speech(page);const session=await start(request,title);
 await page.goto(`/session/${session.id}`);
 await page.getByRole('button',{name:'Autoplay demo'}).click();
 await expect(page.getByRole('button',{name:'Stop & take over'})).toBeVisible();
 await page.screenshot({path:`../.artifacts/e2e/autoplay-${title.includes('Pi')?'pi':'design'}-playing.png`,fullPage:true});
 await expect(page.getByRole('dialog')).toBeVisible({timeout:90000});
 await expect(page.getByText('Scripted example feedback; not a live assessment.')).toBeVisible();
 await expect(page.getByRole('heading',{name:'Next attempt'})).toBeVisible();
 const saved=await (await request.get(`/api/v2/sessions/${session.id}`)).json();
 expect(saved.events.some((e:any)=>e.kind==='note'&&e.payload.demo_autoplay===true)).toBe(true);
 expect(saved.events.some((e:any)=>e.actor==='candidate'&&e.kind==='turn'&&e.payload.text.includes(mistake))).toBe(true);
 expect(saved.events.filter((e:any)=>e.actor==='interviewer'&&e.kind==='turn').length).toBeGreaterThan(1);
 if(title.includes('Pi')){
  expect(saved.events.filter((e:any)=>['command','edit','part_drop'].includes(e.kind)).length).toBeGreaterThan(10);
 }else{
  expect(saved.events.some((e:any)=>e.kind==='stroke')).toBe(true);
  expect(saved.events.some((e:any)=>e.payload.board_snapshot&&e.payload.artifact_id)).toBe(true);
 }
 const report=await (await request.get(`/api/v2/sessions/${session.id}/report`)).json();
 expect(report.status).toBe('graded');
 expect(report.scores).toEqual([]);expect(report.evaluators).toEqual([]);
 expect(saved.engine_state.scripted_demo).toBe(true);
});

test('Stop during speech saves no subsequent actions and restores manual practice',async({page,request})=>{
 await speech(page,true);const session=await start(request,'System design: whiteboard');
 await page.setViewportSize({width:390,height:844});
 await page.goto(`/session/${session.id}`);await page.getByRole('button',{name:'Autoplay demo'}).click();
 await expect(page.getByRole('button',{name:'Stop & take over'})).toBeVisible();
 await expect(page.getByLabel('Demo playback').getByRole('status')).toContainText('Dana is speaking');
 await page.getByRole('button',{name:'Stop & take over'}).click();
 await expect(page.getByRole('button',{name:'Autoplay demo'})).toBeVisible();
 const before=await (await request.get(`/api/v2/sessions/${session.id}/events`)).json();
 // Longer than a normal text-fallback continuation; stopped playback must remain idle.
 await page.waitForTimeout(1200);
 const after=await (await request.get(`/api/v2/sessions/${session.id}/events`)).json();
 expect(after).toEqual(before);
 expect(after.some((e:any)=>e.actor==='candidate'&&e.kind==='turn')).toBe(false);
 await expect(page.getByLabel('Your answer')).toBeEnabled();
 await page.getByLabel('Your answer').fill('What request volume should we support?');
 await expect(page.getByRole('button',{name:'Send',exact:true})).toBeEnabled();
 await page.screenshot({path:'../.artifacts/e2e/autoplay-mobile-stopped.png',fullPage:true});
});

