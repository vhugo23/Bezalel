import { useEffect, useImperativeHandle, useMemo, useRef, useState, type Ref } from 'react';
import { CaptureUpdateAction, Excalidraw, convertToExcalidrawElements, exportToBlob } from '@excalidraw/excalidraw';
import type { ExcalidrawElementSkeleton } from '@excalidraw/excalidraw/data/transform';
import type { ExcalidrawElement } from '@excalidraw/excalidraw/element/types';
import type { AppState, ExcalidrawImperativeAPI } from '@excalidraw/excalidraw/types';
import '@excalidraw/excalidraw/index.css';
import { changedItems, elementBounds, isDana, reconcile, unsupported, type BoardElementJSON, type BoardItem } from '../lib/boardElements';

declare global { interface Window { EXCALIDRAW_ASSET_PATH?: string|string[] } }
// Fonts are served by the app (see vite.config.ts), not a third-party CDN.
window.EXCALIDRAW_ASSET_PATH='/excalidraw/';

export type BoardHandle={
  /** Hand any unsaved local edits to onEdit now instead of after the idle delay. */
  flush:()=>void;
  /** PNG data URL of the candidate's elements only. */
  exportPng:()=>Promise<string>;
  convert:(skeletons:ExcalidrawElementSkeleton[])=>BoardElementJSON[];
};
type Props={
  saved:ReadonlyMap<string,BoardItem>;
  /** Read-only elements shown as-is (legacy fixed-board strokes). */
  extra?:ExcalidrawElementSkeleton[];
  overlay:ExcalidrawElementSkeleton[];
  readOnly:boolean;
  label:string;
  onEdit:(items:BoardItem[])=>void;
  onInteracting?:(busy:boolean)=>void;
  onUnsupported?:()=>void;
  /** Shown as a small fixed pill in the corner, so saving never moves the layout. */
  saveState?:SaveState;
  saveError?:string;
  onRetry?:()=>void;
  /** Quiet shortcut beside Excalidraw's help button. */
  onDemo?:()=>void;
  ref?:Ref<BoardHandle>;
};
export type SaveState='saved'|'saving'|'failed';

// Quick saves finish before the pill would change, so "Saving" only appears when a save is actually slow.
function SavePill({state,error,onRetry}:{state:SaveState;error?:string;onRetry?:()=>void}){
  const [slow,setSlow]=useState(false);
  useEffect(()=>{if(state!=='saving'){setSlow(false);return;}const t=setTimeout(()=>setSlow(true),350);return()=>clearTimeout(t);},[state]);
  const shown=state==='saving'&&!slow?'saved':state;
  if(shown==='failed')return <button type="button" className="save-pill failed" data-state="failed" onClick={onRetry} title={error?`${error} Tap to retry.`:'Tap to retry.'}><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5"/><path d="M8 4.8v3.6M8 11.1v.1"/></svg>Not saved</button>;
  return <span className={`save-pill ${shown}`} data-state={state} role="status" aria-live="polite">{shown==='saving'?<span className="save-spin" aria-hidden="true"/>:<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5"/><path d="m5.2 8.2 1.9 1.9 3.7-3.9"/></svg>}{shown==='saving'?'Saving':'Saved'}</span>;
}
type El=BoardElementJSON;
const convert=(skeletons:ExcalidrawElementSkeleton[])=>convertToExcalidrawElements(skeletons,{regenerateIds:false}) as unknown as El[];
const asScene=(els:readonly El[])=>els as unknown as ExcalidrawElement[];
const interacting=(s:AppState)=>!!(s.newElement||s.resizingElement||s.selectedElementsAreBeingDragged||s.editingTextElement||s.multiElement||s.isRotating||s.selectionElement);

export default function BoardCanvas({saved,extra,overlay,readOnly,label,onEdit,onInteracting,onUnsupported,saveState,saveError,onRetry,onDemo,ref}:Props){
  const api=useRef<ExcalidrawImperativeAPI|null>(null),known=useRef(new Map<string,number>()),busy=useRef(false),stale=useRef(false);
  const timer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined),framing=useRef<ReturnType<typeof setTimeout>|undefined>(undefined);
  const props=useRef({saved,readOnly,onEdit,onInteracting,onUnsupported});props.current={saved,readOnly,onEdit,onInteracting,onUnsupported};
  // Legacy strokes and Dana's marks are converted once per change; Dana's are locked and never saved.
  const legacy=useMemo(()=>convert(extra??[]),[JSON.stringify(extra??[])]);
  const dana=useMemo(()=>convert(overlay).map(e=>({...e,customData:{dana:true},locked:true})),[JSON.stringify(overlay)]);
  const scene=useRef({legacy,dana});scene.current={legacy,dana};

  const remember=()=>{
    for(const item of props.current.saved.values())if((known.current.get(item.id)??0)<item.version)known.current.set(item.id,item.version);
    for(const el of scene.current.legacy)if(!known.current.has(el.id))known.current.set(el.id,el.version);
  };
  const emit=()=>{
    const a=api.current;if(!a||props.current.readOnly)return;
    const els=a.getSceneElementsIncludingDeleted() as unknown as readonly El[];
    const bad=unsupported(els);
    if(bad.length){
      const ids=new Set(bad.map(e=>e.id));
      a.updateScene({elements:asScene(els.map(e=>ids.has(e.id)?{...e,isDeleted:true}:e)),captureUpdate:CaptureUpdateAction.NEVER});
      props.current.onUnsupported?.();
    }
    const changed=changedItems(els,known.current,props.current.saved);
    if(!changed.length)return;
    for(const item of changed)known.current.set(item.id,item.version);
    props.current.onEdit(changed);
  };
  const sync=()=>{
    const a=api.current;if(!a)return;
    // Never yank an element out from under the pointer; catch up when the gesture ends.
    if(busy.current){stale.current=true;return;}
    stale.current=false;remember();
    const local=a.getSceneElementsIncludingDeleted() as unknown as readonly El[];
    const candidate=local.filter(e=>!isDana(e)),merged=reconcile(candidate,props.current.saved)??candidate;
    const missing=scene.current.legacy.filter(e=>!merged.some(m=>m.id===e.id));
    const shownDana=local.filter(isDana).map(e=>e.id).join(),wantDana=scene.current.dana.map(e=>e.id).join();
    if(merged===candidate&&!missing.length&&shownDana===wantDana)return;
    const wasEmpty=!candidate.some(e=>!e.isDeleted);
    a.updateScene({elements:asScene([...merged,...missing,...scene.current.dana]),captureUpdate:CaptureUpdateAction.NEVER});
    // A board that fills in from elsewhere (the demo, the iPad, a reload) is framed so all of it shows.
    // Saved elements can stream in over several updates; frame once they settle.
    if((wasEmpty&&merged.some(e=>!e.isDeleted))||framing.current!==undefined){clearTimeout(framing.current);framing.current=setTimeout(()=>{framing.current=undefined;frame();},350);}
  };
  // Frame the board so all of it shows; zoom out only when it does not fit, never past 100%.
  const frame=()=>{
    const a=api.current;if(!a)return;
    const shown=a.getSceneElements().filter(e=>!isDana(e as unknown as El));if(!shown.length)return;
    const b=shown.map(e=>elementBounds(e as unknown as El)),{width,height}=a.getAppState();
    const wide=Math.max(...b.map(x=>x[2]))-Math.min(...b.map(x=>x[0])),tall=Math.max(...b.map(x=>x[3]))-Math.min(...b.map(x=>x[1]));
    const fits=wide<=width*.85&&tall<=height*.75;
    a.scrollToContent(shown,fits?{}:{fitToViewport:true,viewportZoomFactor:.85});
  };
  const idle=()=>{
    if(busy.current){timer.current=setTimeout(idle,400);return;}
    emit();if(stale.current)sync();
  };
  useEffect(sync,[saved,legacy,dana]);
  useEffect(()=>()=>{clearTimeout(timer.current);clearTimeout(framing.current);emit();},[]);
  // Excalidraw measures its box once; the session layout settles (and resizes) after that.
  const host=useRef<HTMLDivElement>(null);
  useEffect(()=>{const el=host.current;if(!el)return;const watch=new ResizeObserver(()=>api.current?.refresh());watch.observe(el);return()=>watch.disconnect();},[]);
  useImperativeHandle(ref,()=>({
    flush:()=>{clearTimeout(timer.current);emit();},
    convert,
    exportPng:async()=>{
      const a=api.current;if(!a)throw new Error('The whiteboard is still loading.');
      const elements=a.getSceneElements().filter(e=>!isDana(e as unknown as El));
      const blob=await exportToBlob({elements,files:a.getFiles(),mimeType:'image/png',maxWidthOrHeight:1600,exportPadding:24,
        appState:{...a.getAppState(),exportBackground:true,viewBackgroundColor:'#ffffff',exportWithDarkMode:false}});
      return await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(new Error('Could not snapshot the whiteboard.'));reader.readAsDataURL(blob);});
    },
  }),[]);

  const initial=useMemo(()=>{remember();const items=reconcile<El>([],saved)??[];return asScene([...items.filter(e=>!e.isDeleted),...legacy.filter(e=>!saved.has(e.id)),...dana]);},[]);
  const count=useMemo(()=>[...saved.values()].filter(i=>!i.element.isDeleted).length,[saved]);
  return <div ref={host} className="excalidraw-host" aria-label={label} data-dana-marks={dana.length} data-saved-elements={count} data-readonly={readOnly||undefined}>
    <Excalidraw
      excalidrawAPI={a=>{api.current=a;setTimeout(()=>{a.refresh();sync();frame();});}}
      initialData={{elements:initial,appState:{viewBackgroundColor:'#ffffff'}}}
      onChange={(_,state)=>{
        const now=interacting(state);
        if(now!==busy.current){busy.current=now;props.current.onInteracting?.(now);}
        clearTimeout(timer.current);timer.current=setTimeout(idle,now?600:350);
      }}
      viewModeEnabled={readOnly}
      handleKeyboardGlobally={false}
      autoFocus={false}
      UIOptions={{tools:{image:false},canvasActions:{loadScene:false,saveToActiveFile:false,export:false,saveAsImage:false,toggleTheme:false,changeViewBackgroundColor:false,clearCanvas:true}}}
    />
    <div className="board-corner">
      {saveState&&<SavePill state={saveState} error={saveError} onRetry={onRetry}/>}
      {onDemo&&<button type="button" className="board-demo" onClick={onDemo} aria-label="Load demo board + explanation" title="Demo board"><b>D</b><svg viewBox="0 0 16 16" aria-hidden="true"><path d="M5.5 4.2v7.6L11.6 8z"/></svg></button>}
    </div>
  </div>;
}
