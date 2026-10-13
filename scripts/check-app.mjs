// Real single-app/embedded-Postgres acceptance. The model endpoint is synthetic.
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('..',import.meta.url));
const port=18080,modelPort=18777,base=`http://127.0.0.1:${port}`;
const model=createServer((req,res)=>{req.resume();req.on('end',()=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify({choices:[{message:{content:'{"reply":"Hello, I’m Dana. Let’s get started."}'}}],usage:{prompt_tokens:1,completion_tokens:1}}));});});
await new Promise(resolve=>model.listen(modelPort,'127.0.0.1',resolve));
let output='';
const child=spawn(process.execPath,['scripts/start.mjs'],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe','ipc'],
 env:{...process.env,PORT:String(port),PREPCREW_DB_PORT:'15434',PREPCREW_DATA_DIR:resolve(root,'.artifacts/packaged-check'),DATABASE_URL:'',V2_DATABASE_SCHEMA:'prepcrew',PUBLIC_BASE_URL:base,PREPCREW_PUBLIC:'false'}});
child.stdout.on('data',data=>{output+=data;});child.stderr.on('data',data=>{output+=data;});
try{
 let ready=false;
 for(let i=0;i<180;i++){
  if(child.exitCode!==null)throw new Error('Packaged app exited during startup: '+output.slice(-2000));
  try{if((await fetch(base+'/api/v2/health')).ok){ready=true;break;}}catch{}
  await new Promise(resolve=>setTimeout(resolve,500));
 }
 assert(ready,'Packaged app did not become ready.');
 assert.match(await (await fetch(base+'/connections')).text(),/<html/);
 const missing=await fetch(base+'/api/v2/not-a-route');
 assert([401,404].includes(missing.status));assert.match(missing.headers.get('content-type'),/application\/json/);
 assert.equal((await fetch(base+'/.env')).status,404);
 const headers={'Content-Type':'application/json','X-PrepCrew-Request':'1',Origin:base};
 const account=await fetch(base+'/api/v2/auth/register',{method:'POST',headers,body:JSON.stringify({name:'Synthetic packaged acceptance',email:`packaged-${Date.now()}@example.test`,password:'synthetic-long-password-123'})});
 assert.equal(account.status,201);
 const cookie=account.headers.get('set-cookie').split(';')[0];
 const save=await fetch(base+'/api/v2/providers',{method:'PUT',headers:{...headers,Cookie:cookie},body:JSON.stringify({llm:'compatible',model:'synthetic-local-model',base_url:`http://127.0.0.1:${modelPort}/v1`,stt:'local',tts:'local'})});
 assert.equal(save.status,200);assert.equal((await save.json()).ready,true);
 const probe=await fetch(base+'/api/v2/providers/test',{method:'POST',headers:{...headers,Cookie:cookie}});
 assert.equal(probe.status,200);assert.equal((await probe.json()).connected,true);
 console.log('Single-app acceptance passed: embedded Postgres, migrations, same-origin pages/API, private routes and a real BYOB transport roundtrip to a synthetic local model.');
}finally{
 if(child.exitCode===null){child.send('shutdown');await new Promise(resolve=>{child.once('exit',resolve);setTimeout(resolve,15000).unref();});}
 await new Promise(resolve=>model.close(resolve));
}
