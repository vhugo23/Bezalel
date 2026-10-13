import EmbeddedPostgres from 'embedded-postgres';
import {spawn} from 'node:child_process';
import {existsSync,mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
import {randomBytes} from 'node:crypto';
import {createServer} from 'node:net';
const root=fileURLToPath(new URL('..',import.meta.url));
const windows=process.platform==='win32';
const python=resolve(root,windows?'.venv/Scripts/python.exe':'.venv/bin/python');
if(!existsSync(python)||!existsSync(resolve(root,'frontend/dist/index.html')))throw new Error('Run npm run setup first.');
const data=resolve(process.env.PREPCREW_DATA_DIR||resolve(root,'.artifacts/app'));
mkdirSync(data,{recursive:true});
const passwordFile=resolve(data,'database.password');
if(!existsSync(passwordFile))writeFileSync(passwordFile,randomBytes(32).toString('hex'),{mode:0o600,flag:'wx'});
const password=readFileSync(passwordFile,'utf8').trim();
const port=Number(process.env.PORT||8000);
if(process.env.PREPCREW_PUBLIC==='true'&&!process.env.PUBLIC_BASE_URL)throw new Error('Set PUBLIC_BASE_URL to the HTTPS address of your hosted app.');
const dbPort=Number(process.env.PREPCREW_DB_PORT||15433);
let pg,server,stopping=false,pgStarted=false;
const env={...process.env,PYTHONPATH:resolve(root,'backend'),PREPCREW_DATA_DIR:data,
  PREPCREW_WEB_DIST:resolve(root,'frontend/dist'),DATABASE_TIMESCALE:'false',
  MEMORY_BACKEND:'postgres',LEGACY_API_ENABLED:'false',V2_AUTH_TEST_BYPASS:'false',
  PREPCREW_BYOB_ONLY:'true',DEMO_MODE:process.argv.includes('--demo')?'true':'false',
  PREPCREW_LOCAL_APP:process.env.PREPCREW_PUBLIC==='true'?'false':'true',
  PUBLIC_BASE_URL:process.env.PUBLIC_BASE_URL||`http://127.0.0.1:${port}`,
  CORS_ORIGINS:process.env.PUBLIC_BASE_URL||`http://127.0.0.1:${port},http://localhost:${port}`,
  // Existing hackathon .env keys never become someone else's BYOB credentials.
  GEMINI_API_KEY:'',ELEVENLABS_API_KEY:'',BACKBOARD_API_KEY:'',
  DATABASE_URL:process.env.DATABASE_URL||`postgresql://prepcrew:${password}@127.0.0.1:${dbPort}/prepcrew`};
async function run(args){
  await new Promise((resolve,reject)=>{
    const child=spawn(python,args,{cwd:root,env,stdio:'inherit',windowsHide:true});
    child.once('error',reject);child.once('exit',code=>code===0?resolve():reject(new Error(`Setup exited (${code}).`)));
  });
}
async function stop(){
  if(stopping)return;stopping=true;
  if(server&&server.exitCode===null){
    const ended=new Promise(resolve=>{server.once('exit',resolve);setTimeout(resolve,10000).unref();});
    if(windows)spawn('taskkill',['/PID',String(server.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
    else server.kill('SIGTERM');
    await ended;
  }
  if(pgStarted){pgStarted=false;await pg.stop();}
}
process.on('SIGINT',()=>void stop());process.on('SIGTERM',()=>void stop());
process.on('message',message=>{if(message==='shutdown')void stop();});
try{
  await new Promise((resolve,reject)=>{const probe=createServer();probe.once('error',()=>reject(new Error(`Port ${port} is already in use. Close the existing app or choose PORT.`)));probe.listen(port,'127.0.0.1',()=>probe.close(resolve));});
  if(!process.env.DATABASE_URL){
    const dir=resolve(data,'postgres');
    pg=new EmbeddedPostgres({databaseDir:dir,user:'prepcrew',password,port:dbPort,persistent:true,
      authMethod:'scram-sha-256',postgresFlags:['-h','127.0.0.1'],onLog:()=>{},onError:()=>{}});
    if(!existsSync(resolve(dir,'PG_VERSION')))await pg.initialise();
    await pg.start();pgStarted=true;
    const client=pg.getPgClient('postgres','127.0.0.1');await client.connect();
    if(!(await client.query("SELECT 1 FROM pg_database WHERE datname='prepcrew'")).rowCount)await client.query('CREATE DATABASE prepcrew');
    await client.end();
  }
  await run(['-m','alembic','-c','backend/alembic.ini','upgrade','head']);
  server=spawn(python,['-m','uvicorn','app.main:app','--host',process.env.PREPCREW_PUBLIC==='true'?'0.0.0.0':'127.0.0.1','--port',String(port)],{cwd:root,env,stdio:'inherit',windowsHide:true});
  console.log(`PrepCrew is starting at http://127.0.0.1:${port}. Connect your providers in Connections.`);
  await new Promise((resolve,reject)=>{server.once('error',reject);server.once('exit',code=>code===0||stopping?resolve():reject(new Error(`App exited (${code}).`)));});
}finally{await stop();}
