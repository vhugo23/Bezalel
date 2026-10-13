import {spawnSync} from 'node:child_process';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
const root=fileURLToPath(new URL('..',import.meta.url));
const windows=process.platform==='win32';
const python=resolve(root,windows?'.venv/Scripts/python.exe':'.venv/bin/python');
function run(command,args){const result=spawnSync(command,args,{cwd:root,stdio:'inherit',windowsHide:true});if(result.error)throw result.error;if(result.status!==0)process.exit(result.status||1);}
if(!existsSync(python))run(process.env.PYTHON||'python',['-m','venv','.venv']);
run(python,['-m','pip','install','-r','backend/requirements.txt']);
if(!process.env.npm_execpath)throw new Error('Run this setup using npm run setup.');
run(process.execPath,[process.env.npm_execpath,'--prefix','frontend','ci']);
run(process.execPath,[process.env.npm_execpath,'--prefix','frontend','run','build']);
console.log('Ready. Run npm start, then connect your providers in the app.');
