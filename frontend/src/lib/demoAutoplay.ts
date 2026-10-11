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
  'Before choosing a design, what is the expected request rate, and should limits apply per API key or per IP address?',
  'I will use per-key token buckets so callers can burst within a bounded allowance. What availability target and burst limit should I design for?',
 ]},
 {actions:[],board:true,answers:[
  'The gateway sends each request to a rate limiter before the API service. Redis stores the token count and last refill time for each API key. I will read the count, subtract one in the gateway, then write the count back as a separate operation. I think separate reads and writes cannot race because Redis is single threaded.',
  'I have finished the drawing. Please review my board.',
 ]},
 {actions:[],answers:[
  'If Redis is unreachable, I will allow requests using each gateway’s cached token count. I think this preserves the exact global per-key limit even when traffic moves between gateways; no reconciliation or shared coordination is needed.',
  'For concurrency, I still think a separate GET followed by SET is safe across multiple gateways because each Redis command runs sequentially. I would not need a transaction or an atomic Lua script.',
 ]},
];
const pi:DemoStep[]=[
 {actions:[command('curl -I localhost'),command('tail /var/log/nginx/error.log'),command('systemctl status site'),command('curl -I localhost:3000')],answers:[
  'The public endpoint returns 502, but the app responds directly on port 3000. The nginx error references port 3001, so my hypothesis is a mismatched proxy upstream rather than a stopped app.',
 ]},
 {actions:[{kind:'edit',text:config},command('sudo nginx -t'),command('sudo systemctl reload nginx'),command('curl -I localhost')],answers:[
  'I changed only the upstream port, tested the saved nginx configuration, reloaded it, and verified HTTP 200. Testing before reload avoids replacing a working configuration with invalid syntax.',
 ]},
 {actions:[command('curl -I localhost/assets/app.css'),command('ls -l /var/www/site/assets'),command('sudo chmod 644 /var/www/site/assets/app.css'),command('curl -I localhost/assets/app.css')],answers:[
  'The stylesheet was unreadable to nginx. I changed the file to mode 644 and verified HTTP 200. My understanding is that 644 gives every user write permission, which is why nginx can serve it now.',
 ]},
 {actions:[command('df -h'),command('du -sh /var/log/*'),command('sudo truncate -s 0 /var/log/site/access.log'),{kind:'browser',text:'contact'}],answers:[
  'The disk was full because the access log had grown. I truncated that log in place and tested the contact form successfully. I would add rotation and a disk usage alert to stop this recurring.',
 ]},
 {actions:[command('vcgencmd get_throttled'),command('dmesg'),{kind:'part',text:'good'},command('vcgencmd get_throttled')],answers:[
  'I fitted the suitable 5 volt, 3 amp supply and checked again. The value is now 0x50000. I interpret those high bits as current under-voltage, so I think the Pi is still being throttled right now even with the new supply.',
 ]},
];

/** Only the two authored initial scenarios are supported, never generated retests. */
export function demoStep(engineId:string,step:number):DemoStep|undefined {
 const value=(engineId==='linux_fault'?pi:engineId==='conceptual'?design:[])[step];
 return value?{...value,answers:[...value.answers],actions:value.actions.map(a=>({...a}))}:undefined;
}

const originalDesignTitles=['Clarify requirements','Draw and explain','Defend the trade-offs'];
const originalPiTitles=['Read the error','Fix the proxy','Fix the deploy','Free the disk','Check the hardware'];
/** Retests reuse step titles, so the initial scenario prompt must match too. */
export function supportsDemo(session:{engine_id:string;opening?:string;title?:string;steps?:{title:string;surface?:string;task?:string}[]}):boolean {
 if(session.title?.startsWith('Retest:'))return false;
 const titles=session.engine_id==='conceptual'?originalDesignTitles:session.engine_id==='linux_fault'?originalPiTitles:[];
 if(!titles.length||session.steps?.length!==titles.length||session.steps.some((s,i)=>s.title!==titles[i]))return false;
 if(session.engine_id==='linux_fault')return session.steps[4].task==='The site works but is slow. Investigate power and throttling, change a suitable part, and check again.';
 return !!session.opening?.endsWith('Design a rate limiter for a public API. Before you draw anything, ask me what you need to know.');
}

export function demoBoardSkeletons():ExcalidrawElementSkeleton[] {
 return legacyToSkeletons((sample as Stroke[]).map(s=>s.kind==='rect'?{...s,label:''}:s)).concat(
  (sample as Stroke[]).filter(s=>s.kind==='rect'&&s.label).map(s=>({
   type:'text' as const,id:`${s.id}-label`,x:s.points[0].x+10,y:s.points[0].y+23,text:s.label,fontSize:16,
  })));
}

/** Lazy import keeps Excalidraw out of pages that do not play the design demo. */
export async function demoBoardItems():Promise<BoardItem[]> {
 const {convertToExcalidrawElements}=await import('@excalidraw/excalidraw');
 return convertToExcalidrawElements(demoBoardSkeletons(),{regenerateIds:false}).map(element=>toItem(element as unknown as BoardItem['element']));
}

export async function demoBoardPng(items:BoardItem[]):Promise<string> {
 const {exportToBlob}=await import('@excalidraw/excalidraw');
 const elements=items.map(item=>item.element) as unknown as import('@excalidraw/excalidraw/element/types').ExcalidrawElement[];
 const blob=await exportToBlob({elements,files:{},mimeType:'image/png',maxWidthOrHeight:1600,exportPadding:24,
  appState:{exportBackground:true,viewBackgroundColor:'#ffffff',exportWithDarkMode:false}});
 const png=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(new Error('Could not snapshot the demo drawing.'));reader.readAsDataURL(blob);});
 return png;
}

export async function demoBoardSnapshot():Promise<{elements:BoardItem[];png:string}> {
 const elements=await demoBoardItems();return {elements,png:await demoBoardPng(elements)};
}
