import {test,expect,type Page} from '@playwright/test';
test('BYOB connections are private, saved keys are never returned, and disconnect does not affect another account',async({page,browser})=>{
 test.skip(process.env.V2_AUTH_TEST_BYPASS!=='false','Run with backend/scripts/e2e.py --auth connections.spec.ts');
 const stamp=Date.now();
 async function register(target:Page,suffix:string){
  await target.goto('/plan');await target.getByRole('button',{name:'New here? Create an account'}).click();
  await target.getByLabel('Your name').fill('Synthetic connections '+suffix);
  await target.getByLabel('Email',{exact:true}).fill(`connections-${suffix}-${stamp}@example.test`);
  await target.getByLabel('Password',{exact:true}).fill('synthetic-password-long-enough');
  await target.getByRole('button',{name:'Create account',exact:true}).click();
  await expect(target.getByRole('region',{name:'PrepCrew story intro'})).toBeVisible();
  await target.goto('/connections');
  await expect(target.getByRole('heading',{name:'Make Dana yours.'})).toBeVisible();
 }
 await register(page,'a');
 await page.getByLabel('Provider',{exact:true}).selectOption('openai');
 await page.getByLabel('Model ID',{exact:true}).fill('synthetic-model');
 await page.getByLabel('API key',{exact:true}).fill('synthetic-connection-secret-a');
 await page.getByRole('button',{name:'Save connections',exact:true}).click();
 await expect(page.getByText('Connections saved.',{exact:false})).toBeVisible();
 const saved=await (await page.request.get('/api/v2/providers')).json();
 expect(saved.ready).toBe(true);expect(saved.has_llm_key).toBe(true);
 expect(JSON.stringify(saved)).not.toContain('synthetic-connection-secret-a');
 await page.reload();await expect(page.getByLabel('Model ID',{exact:true})).toHaveValue('synthetic-model');
 await expect(page.getByLabel('API key',{exact:true})).toHaveValue('');
 await page.getByLabel('Voice engine',{exact:true}).selectOption('openai');
 await page.getByRole('button',{name:'Save connections',exact:true}).click();
 await expect(page.getByText('Connections saved.',{exact:false})).toBeVisible();
 expect((await (await page.request.get('/api/v2/providers')).json()).has_openai_speech_key).toBe(true);
 const exported=await (await page.request.get('/api/v2/account/export')).json();
 expect(JSON.stringify(exported)).not.toContain('synthetic-connection-secret-a');
 const other=await browser.newContext({baseURL:process.env.PREPCREW_E2E_ORIGIN});const b=await other.newPage();
 try{
  await register(b,'b');expect((await (await b.request.get('/api/v2/providers')).json()).has_llm_key).toBe(false);
  await b.getByLabel('Provider',{exact:true}).selectOption('anthropic');await b.getByLabel('Model ID',{exact:true}).fill('synthetic-other-model');
  await b.getByLabel('API key',{exact:true}).fill('synthetic-connection-secret-b');await b.getByRole('button',{name:'Save connections',exact:true}).click();
  await expect(b.getByText('Connections saved.',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Disconnect all providers',exact:true}).click();
  await expect(page.getByText('All saved provider keys removed.',{exact:false})).toBeVisible();
  expect((await (await page.request.get('/api/v2/providers')).json()).has_llm_key).toBe(false);
  const untouched=await (await b.request.get('/api/v2/providers')).json();expect(untouched.has_llm_key).toBe(true);expect(untouched.model).toBe('synthetic-other-model');
  await b.screenshot({path:'../.artifacts/e2e/connections.png',fullPage:true});
 }finally{await other.close();}
});
