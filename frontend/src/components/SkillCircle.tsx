import type { Model } from '../api/client';
const p=(a:number,r:number)=>`${100+r*Math.cos(a*Math.PI/180)},${100+r*Math.sin(a*Math.PI/180)}`;
const arc=(a:number,b:number,r:number)=>`M${p(a,r)} A${r} ${r} 0 0 1 ${p(b,r)}`;
const wedge=(a:number,b:number,r:number)=>`M${p(a,30)} L${p(a,r)} A${r} ${r} 0 0 1 ${p(b,r)} L${p(b,30)} A30 30 0 0 0 ${p(a,30)}Z`;
export type CircleSkill=Model<'Skill'>&{sample?:boolean};
export function SkillCircle({skills,active=null,onActive}:{skills:CircleSkill[];active?:string|null;onActive?:(id:string|null)=>void}) {
 const assessed=skills.filter(s=>s.score!==null);const avg=assessed.length?Math.round(assessed.reduce((a,s)=>a+(s.score||0),0)/assessed.length):null;
 const focus=skills.find(s=>s.id===active);
 return <svg viewBox="0 0 200 200" width="264" height="264" className={`scirc ${focus?'has-active':''}`} role="img" aria-label={`Skill circle: ${assessed.length} of ${skills.length} assessed. ${avg===null?'No scores yet.':`Average ${avg}.`}`} onMouseLeave={()=>onActive?.(null)}>
  {skills.map((s,i)=>{
   const a=-90+i*360/skills.length+1.8,b=-90+(i+1)*360/skills.length-1.8,mid=(a+b)/2*Math.PI/180;
   // The hovered wedge slides a few units out along its bisector.
   const on=s.id===active,dx=on?Math.cos(mid)*4:0,dy=on?Math.sin(mid)*4:0;
   return <g key={s.id} className={`sw ${on?'on':''}`} style={{transform:`translate(${dx}px,${dy}px)`,animationDelay:`${i*70}ms`}} tabIndex={0} role="button" aria-label={`${s.name}: ${s.score??'not assessed'}${s.sample?' (sample)':''}, target ${s.target}`}
     onMouseEnter={()=>onActive?.(s.id)} onFocus={()=>onActive?.(s.id)} onBlur={()=>onActive?.(null)}>
    <title>{s.name}: {s.score??'not assessed'}{s.sample?' · sample score':''} · target {s.target}</title>
    <path className="sw-bg" d={wedge(a,b,94)} strokeDasharray={s.score===null?'3 3':undefined}/>
    {s.score!==null&&s.score>0&&<path className="sw-fill" d={wedge(a,b,30+64*s.score/100)} fill={s.score<s.target-25?'#f59e0b':'#6366f1'} opacity={s.estimate||s.sample?.6:.95}/>}
    <path className="sw-target" d={arc(a+1,b-1,30+64*s.target/100)} fill="none"/>
   </g>;})}
  <circle cx="100" cy="100" r="27" fill="white" stroke="rgba(30,32,80,.1)"/>
  {focus?<><text x="100" y="103" textAnchor="middle" fontSize="18" fontWeight="600" className="scirc-num">{focus.score??'—'}</text><text x="100" y="114" textAnchor="middle" fontSize="6.5" fill="#71717a">{focus.name.length>16?focus.name.slice(0,15)+'…':focus.name}</text></>
   :<><text x="100" y="104" textAnchor="middle" fontSize={avg===null?12:20} fontWeight="600">{avg??'New'}</text>{avg!==null&&<text x="100" y="116" textAnchor="middle" fontSize="7.5" fill="#71717a">average</text>}</>}
 </svg>;
}
