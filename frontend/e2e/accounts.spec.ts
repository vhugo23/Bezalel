import { test, expect } from '@playwright/test';

test('accounts isolate plans, sessions, sources, jobs and sockets and restore cross-device history',async({browser,page})=>{
 test.skip(process.env.V2_AUTH_TEST_BYPASS!=='false','Run this journey with backend/scripts/e2e.py --auth accounts.spec.ts');
 const protection={'X-PrepCrew-Request':'1'};
 const password='synthetic-acceptance-password-123';
 const stamp=Date.now();
 await page.goto('/plan');
 await page.screenshot({path:'../.artifacts/e2e/accounts-signin.png',fullPage:true});
 await page.getByRole('button',{name:'New here? Create an account'}).click();
 await page.getByLabel('Your name').fill('Synthetic account A');
 await page.getByLabel('Email',{exact:true}).fill(`a-${stamp}@example.test`);
 await page.getByLabel('Password',{exact:true}).fill(password);
 await page.getByRole('button',{name:'Create account',exact:true}).click();
 // A new account opens with the story intro; Skip continues to intake.
 await expect(page.getByRole('region',{name:'PrepCrew story intro'})).toBeVisible();
 await page.getByRole('button',{name:'Skip',exact:true}).click();
 await expect(page.getByRole('heading',{name:"Tell us where you're headed."})).toBeVisible();
 const a=(await (await page.request.get('/api/v2/auth/me')).json()).user;
 const cookies=await page.context().cookies();const sessionCookie=cookies.find(c=>c.name==='prepcrew_session')!;
 expect(sessionCookie.httpOnly).toBe(true);expect(sessionCookie.sameSite).toBe('Lax');
 const sourceResponse=await page.request.post('/api/v2/sources',{headers:protection,data:{user_id:a.id,kind:'notes',title:'Synthetic A private source',body:'Synthetic A private source text.'}});
 expect(sourceResponse.status()).toBe(201);const source=await sourceResponse.json();
 const work=await page.request.post(`/api/v2/sources/${source.id}/extract`,{headers:protection,data:{}});expect(work.status()).toBe(202);const job=await work.json();
 const made=await page.request.post('/api/v2/plans',{headers:protection,data:{user_id:a.id,name:a.name,role:'Software engineer',companies:[],struggles:['System design'],question:'Design an API rate limiter.'}});
 expect(made.ok()).toBe(true);const plan=await made.json();
 const track=plan.tracks.find((t:{title:string})=>t.title==='System design: whiteboard');
 const started=await page.request.post('/api/v2/sessions',{headers:protection,data:{track_id:track.id,consent:true}});expect(started.ok()).toBe(true);const interview=await started.json();
 await page.goto(`/session/${interview.id}`);await expect(page.getByRole('log',{name:'Interview transcript'})).toBeVisible();
 await page.getByRole('link',{name:'History',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Pick up where you left off.'})).toBeVisible();
 await expect(page.getByRole('link',{name:'Resume interview'})).toBeVisible();
 await page.screenshot({path:'../.artifacts/e2e/accounts-history.png',fullPage:true});

 const baseURL=process.env.PREPCREW_E2E_ORIGIN!;
 const b=await browser.newContext({baseURL});const bPage=await b.newPage();
 const bRegistration=await b.request.post('/api/v2/auth/register',{headers:protection,data:{name:'Synthetic account B',email:`b-${stamp}@example.test`,password}});
 expect(bRegistration.status()).toBe(201);const bUser=(await bRegistration.json()).user;
 const aExportResponse=await page.request.get('/api/v2/account/export');
 expect(aExportResponse.ok()).toBe(true);expect(aExportResponse.headers()['cache-control']).toBe('no-store');
 const aExport=await aExportResponse.json();
 expect(aExport.account.id).toBe(a.id);expect(aExport.account.email).toBe(a.email);
 expect(aExport.data.source_documents.some((s:{id:string})=>s.id===source.id)).toBe(true);
 expect(aExport.data.sessions.some((s:{id:string})=>s.id===interview.id)).toBe(true);
 expect(aExport.manifest.limits.truncated).toBe(false);
 expect(JSON.stringify(aExport)).not.toContain('password_hash');
 expect(JSON.stringify(aExport)).not.toContain('token_hash');
 const bExport=await (await b.request.get('/api/v2/account/export')).json();
 expect(bExport.account.id).toBe(bUser.id);expect(bExport.data.sessions).toEqual([]);
 expect(JSON.stringify(bExport)).not.toContain(source.id);expect(JSON.stringify(bExport)).not.toContain(interview.id);
 expect((await b.request.post(`/api/v2/sessions/${interview.id}/socket-ticket`,{headers:protection,data:{channel:'events'}})).status()).toBe(404);
 const ticketResponse=await page.request.post(`/api/v2/sessions/${interview.id}/socket-ticket`,{headers:protection,data:{channel:'events'}});
 expect(ticketResponse.ok()).toBe(true);const ticket=await ticketResponse.json();expect(ticket.expires_in_seconds).toBe(45);
 const direct=await browser.newContext({baseURL:process.env.PREPCREW_E2E_ORIGIN!});const directPage=await direct.newPage();await directPage.goto('/privacy');
 async function upgrade(token:string,channel='sessions'){
  return directPage.evaluate(({token,sid,channel})=>new Promise<boolean>(resolve=>{
   const ws=new WebSocket(`ws://127.0.0.1:18000/ws/v2/${channel}/${sid}`,['prepcrew',`prepcrew-ticket.${token}`]);
   ws.onopen=()=>{resolve(true);ws.close();};ws.onclose=()=>resolve(false);ws.onerror=()=>resolve(false);
  }),{token,sid:interview.id,channel});
 }
 expect(await upgrade(ticket.token,'voice')).toBe(false);
 const claimed=await Promise.all([upgrade(ticket.token),upgrade(ticket.token)]);expect(claimed.filter(Boolean)).toHaveLength(1);
 expect(await upgrade(ticket.token)).toBe(false);
 await page.getByRole('link',{name:'Account',exact:true}).click();
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download my data'}).click();
 expect((await download).suggestedFilename()).toBe('prepcrew-account.json');
 await expect(page.getByRole('status')).toContainText('Your export is ready.');
 await page.screenshot({path:'../.artifacts/e2e/accounts-export.png',fullPage:true});
 for(const path of [`/plans/${plan.id}`,`/sessions/${interview.id}`,`/sessions/${interview.id}/events`,`/sessions/${interview.id}/report`,`/sessions/${interview.id}/metrics`,`/sources/${source.id}`,`/jobs/${job.id}`,`/users/${a.id}/sources`]){
  expect((await b.request.get('/api/v2'+path)).status(),path).toBe(404);
 }
 expect((await b.request.post('/api/v2/sessions',{headers:protection,data:{track_id:track.id,consent:true}})).status()).toBe(404);
 expect((await b.request.post('/api/v2/plans',{headers:protection,data:{user_id:a.id,name:'Forged',role:'Engineer',companies:[],struggles:[],question:''}})).status()).toBe(403);
 expect((await b.request.post(`/api/v2/sources/upload?user_id=${a.id}&title=Forged`,{headers:{...protection,'Content-Type':'text/plain'},data:'Forged source'})).status()).toBe(403);
 expect((await b.request.post('/api/v2/auth/logout',{data:{}})).status()).toBe(403);
 expect((await b.request.post('/api/v2/auth/logout',{headers:{...protection,Origin:'https://attacker.example'},data:{}})).status()).toBe(403);
 expect((await b.request.get('/api/sessions/'+interview.id)).status()).toBe(404);
 await bPage.goto('/history');await expect(bPage.getByRole('heading',{name:'Your first practice starts here.'})).toBeVisible();
 const foreignSocket=await bPage.evaluate(id=>new Promise<number>(resolve=>{const ws=new WebSocket(`${location.origin.replace('http','ws')}/ws/v2/sessions/${id}`);ws.onclose=e=>resolve(e.code);}),interview.id);
 expect([1006,4404]).toContain(foreignSocket);

 // A clean second device has no browser-local plan ID, but server history restores it.
 const second=await browser.newContext({baseURL});const secondPage=await second.newPage();
 const loggedIn=await second.request.post('/api/v2/auth/login',{headers:protection,data:{email:a.email,password}});expect(loggedIn.ok()).toBe(true);
 await secondPage.goto('/plan');await expect(secondPage.getByRole('heading',{name:`Your plan, ${a.name}.`})).toBeVisible();
 await secondPage.getByRole('link',{name:'History',exact:true}).click();await secondPage.getByRole('link',{name:'Resume interview'}).click();
 await expect(secondPage).toHaveURL(new RegExp(`/session/${interview.id}$`));
 // Cookie theft/replay cannot revive a revoked login session.
 const oldCookies=await page.context().cookies();
 const revokeTicket=await (await page.request.post(`/api/v2/sessions/${interview.id}/socket-ticket`,{headers:protection,data:{channel:'events'}})).json();
 await page.locator('summary[aria-label="Account menu"]').click();await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.getByRole('heading',{name:'Welcome back.'})).toBeVisible();
 expect(await upgrade(revokeTicket.token)).toBe(false);await direct.close();
 expect((await page.request.get(`/api/v2/sessions/${interview.id}`)).status()).toBe(401);
 expect((await page.request.get('/api/v2/account/export')).status()).toBe(401);
 const replay=await browser.newContext({baseURL});await replay.addCookies(oldCookies);
 expect((await replay.request.get('/api/v2/history')).status()).toBe(401);await replay.close();
 // Other devices remain signed in when only this device signs out.
 expect((await second.request.get('/api/v2/history')).status()).toBe(200);
 await page.getByLabel('Email',{exact:true}).fill(bUser.email);await page.getByLabel('Password',{exact:true}).fill(password);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByRole('link',{name:'History',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Your first practice starts here.'})).toBeVisible();
 const browserState=await page.evaluate(()=>JSON.parse(localStorage.getItem('prepcrew-profile-v2')!).state);
 expect(browserState.intake.user_id).toBe(bUser.id);expect(browserState.planId).toBeNull();expect(browserState.intake.source_ids).toEqual([]);
 await b.close();await second.close();
});
