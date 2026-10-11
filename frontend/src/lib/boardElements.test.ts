import { describe, expect, it } from 'vitest';
import type { Annotation, Event, Stroke } from '../api/client';
import { schemas } from '../api/schemas';
import sample from '../../../contracts/examples/circuit_stamps.sample.json';
import demoBoard from '../../../contracts/demo-board.json';
import { activeItems, boardFromEvents, changedItems, danaSkeletons, elementBounds, legacyToSkeletons, markGeometry, mergePending, reconcile, unsupported, validateMarks, type BoardElementJSON, type BoardItem } from './boardElements';

const el=(id:string,over:Partial<BoardElementJSON>={}):BoardElementJSON=>({id,type:'rectangle',version:1,versionNonce:7,isDeleted:false,x:10,y:20,width:100,height:50,angle:0,index:'a0',...over});
const item=(id:string,over:Partial<BoardElementJSON>={}):BoardItem=>{const element=el(id,over);return {id,version:element.version,element};};
let seq=0;
const ev=(payload:Record<string,unknown>,step=1,kind:Event['kind']='stroke',actor='candidate'):Event=>({session_id:'s',seq:++seq,kind,actor,step,payload,ts:new Date(0).toISOString()} as Event);

describe('saved board',()=>{
  it('keeps the newest version per element, remembers deletions and reads legacy strokes',()=>{
    const {latest,legacy}=boardFromEvents([
      ev(item('box',{version:3,x:50})),ev(item('box',{version:2})),ev(item('gone')),ev(item('gone',{version:2,isDeleted:true})),
      ev(item('other'),2),ev({id:'old',kind:'rect',points:[{x:1,y:1},{x:9,y:9}],label:'Old'}),ev({id:'erased',kind:'path',points:[{x:1,y:1}]}),
      ev({remove_strokes:['erased']},1,'note','system'),ev({id:'bad',version:1,element:{id:'other',type:'rectangle'}}),
    ],1);
    expect(latest.get('box')?.element.x).toBe(50);
    expect(latest.get('gone')?.element.isDeleted).toBe(true);
    expect(latest.has('other')).toBe(false);
    expect(legacy.map(s=>s.id)).toEqual(['old']);
    expect(activeItems(latest).map(i=>i.id)).toEqual(['box']);
  });
  it('orders active elements by their drawing order',()=>{
    const latest=new Map([['b',item('b',{index:'a2'})],['a',item('a',{index:'a1'})],['c',item('c',{index:null})]]);
    expect(activeItems(latest).map(i=>i.id)).toEqual(['a','b','c']);
  });
});

describe('local edits',()=>{
  it('reports only new candidate versions worth saving',()=>{
    const saved=new Map([['same',item('same',{version:2})]]);
    const known=new Map([['box',2],['same',2]]);
    const scene=[el('box',{version:3}),el('old',{version:1}),el('dana',{customData:{dana:true}}),el('frame',{type:'frame'}),
      el('scratch',{isDeleted:true,version:4}),el('same',{version:5,versionNonce:99,updated:123}),el('box2',{version:2})];
    expect(changedItems(scene,new Map([...known,['old',1]]),saved).map(i=>`${i.id}:${i.version}`)).toEqual(['box:3','box2:2']);
    expect(unsupported(scene).map(e=>e.id)).toEqual(['frame']);
  });
  it('drops undefined fields so the saved payload equals what the server stores',()=>{
    const [changed]=changedItems([el('box',{link:undefined})],new Map());
    expect('link' in changed.element).toBe(false);
  });
  it('queues only the newest version of each element',()=>{
    expect(mergePending([item('a',{version:2}),item('b')],[item('a',{version:1}),item('a',{version:4}),item('c')]).map(i=>`${i.id}:${i.version}`)).toEqual(['a:4','b:1','c:1']);
  });
});

describe('reconcile',()=>{
  it('lets the saved copy win unless the local one is newer or being edited',()=>{
    const local=[el('mine',{version:5,index:'a1'}),el('theirs',{version:1,index:'a2'}),el('tie',{version:2,versionNonce:1,index:'a3'}),el('editing',{version:1,index:'a4'})];
    const saved=new Map([
      ['mine',item('mine',{version:4,x:999,index:'a1'})],['theirs',item('theirs',{version:2,x:42,index:'a2'})],['tie',item('tie',{version:2,versionNonce:9,x:7,index:'a3'})],
      ['editing',item('editing',{version:9,index:'a4'})],['new',item('new',{index:'a0'})],['ghost',item('ghost',{isDeleted:true,version:3})],
    ]);
    const merged=reconcile(local,saved,new Set(['editing']))!;
    expect(merged.map(e=>e.id)).toEqual(['new','mine','theirs','tie','editing']);
    expect(merged.find(e=>e.id==='mine')?.version).toBe(5);
    expect(merged.find(e=>e.id==='theirs')?.x).toBe(42);
    expect(merged.find(e=>e.id==='tie')?.x).toBe(7);
    expect(merged.find(e=>e.id==='editing')?.version).toBe(1);
    expect(reconcile(merged,saved,new Set(['editing']))).toBeNull();
  });
  it('removes an element another device deleted',()=>{
    const merged=reconcile([el('box')],new Map([['box',item('box',{version:2,isDeleted:true})]]))!;
    expect(merged[0].isDeleted).toBe(true);
  });
});

describe('Dana marks',()=>{
  const mark=(target:string,kind:Annotation['kind']='circle'):Annotation=>({id:'m1',kind,severity:'probe',speech:'Why Redis here, and what happens when it is down?',target,geometry:{},target_seq:1,event_seq:2});
  it('measures rotated and linear elements like the server does',()=>{
    expect(elementBounds(el('b',{x:-500,y:2000}))).toEqual([-500,2000,-400,2050]);
    expect(elementBounds(el('r',{x:0,y:0,width:100,height:50,angle:Math.PI/2})).map(Math.round)).toEqual([25,-25,75,75]);
    expect(elementBounds(el('a',{type:'arrow',x:10,y:10,points:[[0,0],[-20,30],[40,5]]}))).toEqual([-10,10,50,40]);
    expect(markGeometry(el('b'))).toEqual({x:-2,y:8,w:124,h:74,cx:60,cy:45,rx:62,ry:37});
  });
  it('targets only elements on the board and draws locked, tagged marks',()=>{
    const items=[item('redis')];
    const checked=validateMarks([mark('redis')],items);
    expect(checked[0].geometry.w).toBe(124);
    expect(()=>validateMarks([mark('missing')],items)).toThrow('unknown element');
    expect(()=>validateMarks(Array(5).fill(mark('redis')),items)).toThrow();
    for(const kind of ['circle','arrow','underline','highlight','sticky','cross','check'] as const){
      const shapes=danaSkeletons(validateMarks([mark('redis',kind)],items));
      expect(shapes.length).toBeGreaterThan(0);
      for(const s of shapes)expect(s).toMatchObject({customData:{dana:true},locked:true});
    }
  });
});

describe('legacy strokes',()=>{
  it('keeps ids and labels for the demo board and circuit stamps',()=>{
    const demo=legacyToSkeletons(demoBoard.map(raw=>schemas.Stroke.parse(raw) as Stroke));
    expect(demo.map(s=>s.id)).toEqual(demoBoard.map(s=>s.id));
    expect(demo.find(s=>s.id==='limiter')).toMatchObject({type:'rectangle',x:460,y:200,width:170,height:64,label:{text:'Rate limiter'}});
    expect(demo.find(s=>s.id==='a1')).toMatchObject({type:'arrow',x:170,y:232,points:[[0,0],[70,0]]});
    const stamps=(sample as {strokes:unknown[]}).strokes.map(raw=>schemas.Stroke.parse(raw) as Stroke);
    const converted=legacyToSkeletons(stamps);
    expect(converted).toHaveLength(stamps.length);
    expect(new Set(converted.map(s=>s.type))).toEqual(new Set(['line','arrow','text']));
  });
});
