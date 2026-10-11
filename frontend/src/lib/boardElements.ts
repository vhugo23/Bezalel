import type { ExcalidrawElementSkeleton } from '@excalidraw/excalidraw/data/transform';
import type { Annotation, Event, Stroke } from '../api/client';
import { schemas } from '../api/schemas';

// Pure helpers for the Excalidraw whiteboard. No React, no DOM, no Excalidraw runtime.
// The server keeps every saved element version; the newest version of an id wins and
// `isDeleted` versions remove it. Dana's marks are local-only elements tagged customData.dana.

export type BoardElementJSON = Record<string,unknown>&{
  id:string;type:string;version:number;versionNonce?:number;isDeleted:boolean;
  x:number;y:number;width:number;height:number;angle:number;
  points?:readonly (readonly [number,number])[];containerId?:string|null;text?:string;
  customData?:Record<string,unknown>;index?:string|null;locked?:boolean;
};
export type BoardItem={id:string;version:number;element:BoardElementJSON};
export const BOARD_TYPES=new Set(['rectangle','diamond','ellipse','arrow','line','freedraw','text']);
const LINEAR=new Set(['arrow','line','freedraw']);
export const MAX_BATCH=200;

const finite=(v:unknown)=>typeof v==='number'&&Number.isFinite(v);
/** A saved element, checked as the server checks it: the record must describe its own element. */
export function parseItem(payload:unknown):BoardItem|null{
  const parsed=schemas.BoardElement.safeParse(payload);if(!parsed.success)return null;
  const item=parsed.data as BoardItem,e=item.element;
  const ok=e.id===item.id&&e.version===item.version&&typeof e.isDeleted==='boolean'&&BOARD_TYPES.has(e.type)&&['x','y','width','height','angle'].every(k=>finite(e[k]));
  return ok?item:null;
}

/** Newest saved version per element for one step (deleted ones included, so reconcile can remove them),
 *  plus any legacy fixed-board strokes from sessions recorded before the Excalidraw board. */
export function boardFromEvents(events:readonly Event[],step:number){
  const latest=new Map<string,BoardItem>(),legacy=new Map<string,Stroke>();
  for(const e of events){
    if(e.step!==step)continue;
    if(e.kind==='stroke'&&e.actor==='candidate'){
      const item=parseItem(e.payload);
      if(item){const known=latest.get(item.id);if(!known||item.version>=known.version)latest.set(item.id,item);continue;}
      const old=schemas.Stroke.safeParse(e.payload);if(old.success)legacy.set((old.data as Stroke).id,old.data as Stroke);
    }
    if(e.kind==='note'&&Array.isArray(e.payload.remove_strokes))for(const id of e.payload.remove_strokes)legacy.delete(String(id));
  }
  return {latest,legacy:[...legacy.values()]};
}

const byIndex=(a:{index?:string|null;id:string},b:{index?:string|null;id:string})=>{
  const x=a.index??'￿',y=b.index??'￿';return x<y?-1:x>y?1:a.id<b.id?-1:a.id>b.id?1:0;
};
export function activeItems(latest:ReadonlyMap<string,BoardItem>):BoardItem[]{
  return [...latest.values()].filter(i=>!i.element.isDeleted).sort((a,b)=>byIndex(a.element,b.element));
}
export const boardFingerprint=(items:readonly BoardItem[])=>items.map(i=>`${i.id}:${i.version}`).sort().join('|');

/** Newest version per id. Saves are queued in order, so one save carries every newer edit. */
export function mergePending(old:readonly BoardItem[],changed:readonly BoardItem[]){
  const next=new Map(old.map(i=>[i.id,i]));
  for(const item of changed)if((next.get(item.id)?.version??0)<item.version)next.set(item.id,item);
  return [...next.values()];
}

export const isDana=(el:{customData?:Record<string,unknown>|null})=>el.customData?.dana===true;
const json=<T,>(value:T):T=>JSON.parse(JSON.stringify(value)) as T;
export function toItem(el:BoardElementJSON):BoardItem{return {id:el.id,version:el.version,element:json(el)};}

/** Candidate elements the editor can make but the board does not keep (frames, embeds, images). */
export function unsupported(elements:readonly BoardElementJSON[]){
  return elements.filter(el=>!el.isDeleted&&!isDana(el)&&!BOARD_TYPES.has(el.type));
}

const VOLATILE=new Set(['version','versionNonce','updated','seed']);
const content=(el:Record<string,unknown>)=>JSON.stringify(Object.keys(el).filter(k=>!VOLATILE.has(k)&&el[k]!==undefined).sort().map(k=>[k,el[k]]));

/** Candidate element versions newer than anything saved or already sent. A version bump that changes
 *  nothing visible (the editor re-measuring text after fonts load, say) is not worth a new record. */
export function changedItems(elements:readonly BoardElementJSON[],known:ReadonlyMap<string,number>,saved:ReadonlyMap<string,BoardItem>=new Map()):BoardItem[]{
  const out:BoardItem[]=[];
  for(const el of elements){
    if(isDana(el)||!BOARD_TYPES.has(el.type))continue;
    const seen=known.get(el.id);
    // Something drawn and erased before it was ever saved needs no record.
    if(seen===undefined&&el.isDeleted)continue;
    if(el.version<=(seen??0))continue;
    const kept=saved.get(el.id);
    if(kept&&content(kept.element)===content(el))continue;
    out.push(toItem(el));
  }
  return out;
}

/** Merge saved versions into the local scene. The server is the source of truth: a saved version wins
 *  unless the local copy is newer (an edit still being saved). Elements being edited are left alone.
 *  Returns null when nothing changes. */
export function reconcile<T extends BoardElementJSON>(local:readonly T[],saved:ReadonlyMap<string,BoardItem>,editing:ReadonlySet<string>=new Set()):T[]|null{
  const byId=new Map<string,T>(local.map(e=>[e.id,e]));let changed=false;
  for(const item of saved.values()){
    if(editing.has(item.id))continue;
    const mine=byId.get(item.id);
    if(!mine||item.version>mine.version||(item.version===mine.version&&item.element.versionNonce!==mine.versionNonce)){
      if(!mine&&item.element.isDeleted)continue;
      byId.set(item.id,json(item.element) as T);changed=true;
    }
  }
  return changed?[...byId.values()].sort(byIndex):null;
}

export function elementBounds(el:BoardElementJSON):[number,number,number,number]{
  if(LINEAR.has(el.type)&&el.points?.length){
    const xs=el.points.map(p=>el.x+p[0]),ys=el.points.map(p=>el.y+p[1]);
    return [Math.min(...xs),Math.min(...ys),Math.max(...xs),Math.max(...ys)];
  }
  const {x,y,width:w,height:h,angle:a}=el;
  if(!a)return [x,y,x+w,y+h];
  const cx=x+w/2,cy=y+h/2,corners=[[-1,-1],[1,-1],[-1,1],[1,1]].map(([sx,sy])=>{const dx=sx*w/2,dy=sy*h/2;return [cx+dx*Math.cos(a)-dy*Math.sin(a),cy+dx*Math.sin(a)+dy*Math.cos(a)];});
  return [Math.min(...corners.map(c=>c[0])),Math.min(...corners.map(c=>c[1])),Math.max(...corners.map(c=>c[0])),Math.max(...corners.map(c=>c[1]))];
}

// Mirrors backend integrity.geometry: the target's bounds with 12px of room.
export function markGeometry(el:BoardElementJSON){
  const [l,t,r,b]=elementBounds(el);const x=l-12,y=t-12,right=r+12,bottom=b+12;
  return {x,y,w:right-x,h:bottom-y,cx:(x+right)/2,cy:(y+bottom)/2,rx:(right-x)/2,ry:(bottom-y)/2};
}

export function validateMarks(marks:readonly Annotation[],items:readonly BoardItem[]):Annotation[]{
  if(marks.length>4||new Set(items.map(i=>i.id)).size!==items.length)throw new Error('Invalid annotation batch');
  return marks.map(mark=>{const target=items.find(i=>i.id===mark.target);if(!target)throw new Error('Annotation refers to an unknown element');return {...mark,geometry:markGeometry(target.element)};});
}

const wrap=(text:string,width=34)=>text.split(/\s+/).reduce<string[]>((lines,word)=>{const last=lines.at(-1);if(last!==undefined&&(last+' '+word).length<=width)lines[lines.length-1]=last+' '+word;else lines.push(word);return lines;},[]).join('\n');

/** Dana's marks as Excalidraw skeletons, drawn beside the candidate's work and never saved as it. */
export function danaSkeletons(marks:readonly Annotation[]):ExcalidrawElementSkeleton[]{
  const out:ExcalidrawElementSkeleton[]=[];
  marks.forEach(m=>{
    const {x,y,w,h,cy}=m.geometry as ReturnType<typeof markGeometry>;
    const color=m.severity==='problem'?'#dc2626':'#0d9488',base={strokeColor:color,strokeWidth:2,roughness:1,customData:{dana:true},locked:true};
    const id=(n:number)=>`dana-${m.id}-${n}`;
    if(m.kind==='circle')out.push({...base,type:'ellipse',id:id(0),x,y,width:w,height:h,backgroundColor:'transparent'});
    else if(m.kind==='highlight')out.push({...base,type:'rectangle',id:id(0),x,y,width:w,height:h,backgroundColor:m.severity==='problem'?'#fecaca':'#99f6e4',fillStyle:'solid',opacity:35,strokeColor:'transparent'});
    else if(m.kind==='underline')out.push({...base,type:'line',id:id(0),x,y:y+h,points:[[0,0],[w,0]]});
    else if(m.kind==='cross')out.push({...base,type:'line',id:id(0),x,y,points:[[0,0],[w,h]]},{...base,type:'line',id:id(1),x:x+w,y,points:[[0,0],[-w,h]]});
    else if(m.kind==='check')out.push({...base,type:'line',id:id(0),x,y,points:[[0,h*.55],[w*.35,h*.9],[w,0]]});
    else if(m.kind==='arrow')out.push({...base,type:'arrow',id:id(0),x:x-96,y:cy,points:[[0,0],[84,0]]});
    else out.push({...base,type:'text',id:id(0),x:x+w+14,y,text:wrap(m.speech.slice(0,160)),fontSize:16,strokeColor:'#115e59'});
  });
  return out;
}

/** Fixed-board strokes (old sessions, the demo board, circuit stamps) as Excalidraw skeletons with the same ids. */
export function legacyToSkeletons(strokes:readonly Stroke[]):ExcalidrawElementSkeleton[]{
  return strokes.flatMap<ExcalidrawElementSkeleton>(s=>{
    const first=s.points[0],last=s.points[s.points.length-1];if(!first)return [];
    const xs=s.points.map(p=>p.x),ys=s.points.map(p=>p.y),x=Math.min(...xs),y=Math.min(...ys);
    if(s.kind==='rect')return [{type:'rectangle',id:s.id,x,y,width:Math.max(...xs)-x,height:Math.max(...ys)-y,roundness:{type:3},...(s.label?{label:{text:s.label,fontSize:16}}:{})}];
    if(s.kind==='text')return [{type:'text',id:s.id,x:first.x,y:first.y-14,text:s.label||'',fontSize:14}];
    const points=s.points.map(p=>[p.x-first.x,p.y-first.y] as [number,number]);
    return [{type:s.kind==='arrow'?'arrow':'line',id:s.id,x:first.x,y:first.y,points:points.length>1?points:[[0,0],[.1,.1]]}];
  });
}
