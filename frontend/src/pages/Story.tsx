import { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { startIntro } from '../story/intro.js';

// Only same-site paths, so a crafted link cannot send someone elsewhere after the intro.
const safeNext=(value:string|null)=>value&&value.startsWith('/')&&!value.startsWith('//')?value:'/plan';

/** The hackathon story intro: twelve rejections, a suspicious email, PrepCrew boots. */
export function StoryPage(){
 const nav=useNavigate(),[params]=useSearchParams(),next=safeNext(params.get('next'));
 const stage=useRef<HTMLDivElement>(null),caption=useRef<HTMLSpanElement>(null),fade=useRef<HTMLDivElement>(null),flash=useRef<HTMLDivElement>(null);
 const controls=useRef<ReturnType<typeof startIntro>|null>(null);
 useEffect(()=>{
  const intro=startIntro({stage:stage.current!,caption:caption.current!,fade:fade.current!,flash:flash.current!,onDone:()=>nav(next,{replace:true})});
  controls.current=intro;
  const key=(e:KeyboardEvent)=>{if(e.key==='Escape')intro.skip();};
  addEventListener('keydown',key);
  return()=>{removeEventListener('keydown',key);intro.dispose();};
 },[]);
 return <section className="story" aria-label="PrepCrew story intro">
  <div ref={stage} className="story-stage"/><div className="story-vig"/><div className="story-grain"/>
  <div ref={fade} className="story-fade"/>
  <div className="story-cap"><span ref={caption} aria-live="polite" style={{opacity:0}}/></div>
  <button type="button" className="story-skip" onClick={()=>controls.current?.skip()}>Skip</button>
  <div ref={flash} className="story-flash"/>
 </section>;
}
