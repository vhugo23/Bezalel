import type { ExcalidrawElementSkeleton } from '@excalidraw/excalidraw/data/transform';
import type { Model, Stroke } from '../api/client';
import type { BoardItem } from './boardElements';
import { legacyToSkeletons, toItem } from './boardElements';
import sample from '../../../contracts/demo-board.json';

/** Authored synthetic candidate, submitted through the ordinary practice APIs.
 * Explicit misconceptions provide evidence for grading; scores are never scripted. */
export type DemoLabAction = Pick<Model<'LabAction'>,'kind'|'text'>;
export type DemoStep = { answers:string[]; actions:DemoLabAction[]; board?:boolean };
const command=(text:string):DemoLabAction=>({kind:'command',text});
const config='server {\n    listen 80;\n    location / {\n        proxy_pass http://127.0.0.1:3000;\n    }\n    location /assets/ {\n        root /var/www/site;\n    }\n}\n';

const design:DemoStep[]=[
 {actions:[],answers:[
  'What traffic and per-key limit should we support?',
  'I will use token buckets. What burst allowance and availability target do we need?',
 ]},
 {actions:[],board:true,answers:[
  'The gateway checks a Redis token bucket before calling the API. I think separate reads and writes cannot race because Redis is single threaded.',
  'Please review my board.',
 ]},
 {actions:[],answers:[
  'If Redis fails, each gateway uses cached tokens. I think exact global limits still hold; no reconciliation or shared coordination is needed.',
  'A separate GET followed by SET should be safe. I would not need a transaction or an atomic Lua script.',
 ]},
];
const pi:DemoStep[]=[
 {actions:[command('curl -I localhost'),command('tail /var/log/nginx/error.log'),command('systemctl status site'),command('curl -I localhost:3000')],answers:[
  'The app works on port 3000. Nginx points to 3001, causing the 502.',
 ]},
 {actions:[{kind:'edit',text:config},command('sudo nginx -t'),command('sudo systemctl reload nginx'),command('curl -I localhost')],answers:[
  'I corrected the port, tested nginx, reloaded, and verified HTTP 200.',
 ]},
 {actions:[command('curl -I localhost/assets/app.css'),command('ls -l /var/www/site/assets'),command('sudo chmod 644 /var/www/site/assets/app.css'),command('curl -I localhost/assets/app.css')],answers:[
  'The stylesheet now returns 200. I think 644 gives every user write permission.',
 ]},
 {actions:[command('df -h'),command('du -sh /var/log/*'),command('sudo truncate -s 0 /var/log/site/access.log'),{kind:'browser',text:'contact'}],answers:[
  'The access log filled the disk. I truncated it and verified the form. Next, add log rotation.',
 ]},
 {actions:[command('vcgencmd get_throttled'),command('dmesg'),{kind:'part',text:'good'},command('vcgencmd get_throttled')],answers:[
  'I fitted the good supply. I interpret high bits as current under-voltage, so I think it is still throttling.',
 ]},
];

/** Only the two authored initial scenarios are supported, never generated retests. */
export function demoStep(engineId:string,step:number):DemoStep|undefined {
 const value=(engineId==='linux_fault'?pi:engineId==='conceptual'?design:[])[step];
 return value?{...value,answers:[...value.answers],actions:value.actions.map(a=>({...a}))}:undefined;
}

const originalDesignTitles=['Clarify requirements','Draw and explain','Defend the trade-offs'];
const originalPiTitles=['Read the error','Fix the proxy','Fix the deploy','Free the disk','Check the hardware'];
/** Personalized opening text is allowed; changed retests have a separate title. */
export function supportsDemo(session:{engine_id:string;opening?:string;title?:string;steps?:{title:string;surface?:string;task?:string}[]}):boolean {
 if(session.title?.startsWith('Retest:'))return false;
 const titles=session.engine_id==='conceptual'?originalDesignTitles:session.engine_id==='linux_fault'?originalPiTitles:[];
 if(!titles.length||session.steps?.length!==titles.length||session.steps.some((s,i)=>s.title!==titles[i]))return false;
 if(session.engine_id==='linux_fault')return session.steps[4].task==='The site works but is slow. Investigate power and throttling, change a suitable part, and check again.';
 return true;
}

export function demoBoardSkeletons():ExcalidrawElementSkeleton[] {
 return legacyToSkeletons((sample as Stroke[]).map(s=>s.kind==='rect'?{...s,label:''}:s)).map(s=>s.type==='rectangle'?{...s,boundElements:[{id:`${s.id}-label`,type:'text' as const}]}:s).concat(
  (sample as Stroke[]).filter(s=>s.kind==='rect'&&s.label).map(s=>({
   type:'text' as const,id:`${s.id}-label`,containerId:s.id,x:s.points[0].x+10,y:s.points[0].y+23,text:s.label,fontSize:16,
  })));
}

/** Lazy import keeps Excalidraw out of pages that do not play the design demo. */
export async function demoBoardItems():Promise<BoardItem[]> {
 const {convertToExcalidrawElements}=await import('@excalidraw/excalidraw');
 return convertToExcalidrawElements(demoBoardSkeletons(),{regenerateIds:false}).map(element=>toItem(element as unknown as BoardItem['element']));
}

export async function demoBoardPng(items:BoardItem[]):Promise<string> {
 const {exportToBlob}=await import('@excalidraw/excalidraw');
 // Export may measure text and adjust element metrics; never mutate the saved snapshot.
 const elements=structuredClone(items.map(item=>item.element)) as unknown as import('@excalidraw/excalidraw/element/types').ExcalidrawElement[];
 const blob=await exportToBlob({elements,files:{},mimeType:'image/png',maxWidthOrHeight:1600,exportPadding:24,
  appState:{exportBackground:true,viewBackgroundColor:'#ffffff',exportWithDarkMode:false}});
 const png=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(new Error('Could not snapshot the demo drawing.'));reader.readAsDataURL(blob);});
 return png;
}

export async function demoBoardSnapshot():Promise<{elements:BoardItem[];png:string}> {
 const elements=await demoBoardItems();return {elements,png:await demoBoardPng(elements)};
}
