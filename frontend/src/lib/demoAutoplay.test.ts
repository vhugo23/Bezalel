import {describe,expect,it,vi} from 'vitest';
import {demoStep,demoBoardSkeletons,demoBoardPng,supportsDemo} from './demoAutoplay';
import {schemas} from '../api/schemas';
import type {BoardItem} from './boardElements';

vi.mock('@excalidraw/excalidraw',()=>({exportToBlob:async({elements}:{elements:{width:number}[]})=>{
 elements[0].width=999;return new Blob(['synthetic PNG']);
}}));

describe('authored demo candidate',()=>{
 it('keeps the saved candidate snapshot unchanged when PNG export adjusts text metrics',async()=>{
  vi.stubGlobal('FileReader',class {result='data:image/png;base64,cG5n';onload?:()=>void;readAsDataURL(){this.onload?.();}});
  try{
   const items:BoardItem[]=[{id:'label',version:1,element:{id:'label',type:'text',version:1,isDeleted:false,x:0,y:0,width:80,height:20,angle:0,text:'Redis'}}];
   const saved=structuredClone(items);
   expect(await demoBoardPng(items)).toContain('data:image/png');
   expect(items).toEqual(saved);
  }finally{vi.unstubAllGlobals();}
 });
 it('refuses changed retests even when their engine and step titles are reused',()=>{
  const original={engine_id:'conceptual',opening:'Design a rate limiter for a public API. Before you draw anything, ask me what you need to know.',steps:['Clarify requirements','Draw and explain','Defend the trade-offs'].map(title=>({title}))};
  expect(supportsDemo(original)).toBe(true);
  expect(supportsDemo({...original,opening:'Design a limiter for a personalized workload.'})).toBe(true);
  expect(supportsDemo({...original,title:'Retest: concurrency'})).toBe(false);
  expect(supportsDemo({...original,steps:[{title:'Changed variant'}]})).toBe(false);
 });
 it('covers exactly the runnable initial scenario steps with bounded valid inputs',()=>{
  for(const [engine,count] of [['conceptual',3],['linux_fault',5]] as const){
   for(let step=0;step<count;step++){
    const script=demoStep(engine,step)!;
    expect(script.answers.length).toBeGreaterThan(0);
    expect(script.answers.length).toBeLessThanOrEqual(3);
    for(const text of script.answers)expect(schemas.TurnInput.safeParse({step,text,board:script.board||false}).success).toBe(true);
    for(const action of script.actions)expect(schemas.LabAction.safeParse({...action,step,revision:0,request_id:'synthetic-action-0001'}).success).toBe(true);
   }
   expect(demoStep(engine,count)).toBeUndefined();
  }
  expect(demoStep('unknown',0)).toBeUndefined();
 });
 it('provides explicit assessable attempted mistakes rather than claiming fabricated grades',()=>{
  expect(demoStep('conceptual',2)!.answers.join(' ')).toContain('would not need a transaction');
  expect(demoStep('conceptual',2)!.answers[0]).toContain('no reconciliation or shared coordination is needed');
  expect(demoStep('linux_fault',2)!.answers.join(' ')).toContain('644 gives every user write permission');
  expect(demoStep('linux_fault',4)!.answers.join(' ')).toContain('high bits as current under-voltage');
  expect(demoBoardSkeletons().length).toBeGreaterThan(5);
  const first=demoBoardSkeletons(),second=demoBoardSkeletons();
  expect(first.map(s=>s.id)).toEqual(second.map(s=>s.id));
  expect(new Set(first.map(s=>s.id)).size).toBe(first.length);
  expect(first.some(s=>s.id==='redis-label')).toBe(true);
  expect(first.filter(s=>s.type==='rectangle').every(s=>!('label' in s))).toBe(true);
  expect(first.find(s=>s.id==='redis-label')).toMatchObject({containerId:'redis'});
  expect(first.find(s=>s.id==='redis')).toMatchObject({boundElements:[{id:'redis-label',type:'text'}]});
 });
 it('returns independent action and answer collections so playback cannot change another run',()=>{
  const first=demoStep('linux_fault',0)!;
  first.answers.length=0;first.actions[0].text='changed';
  expect(demoStep('linux_fault',0)!.answers.length).toBe(1);
  expect(demoStep('linux_fault',0)!.actions[0].text).toBe('curl -I localhost');
 });
});
