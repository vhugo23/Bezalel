import type { Model } from '../api/client';
const p=(a:number,r:number)=>`${100+r*Math.cos(a*Math.PI/180)},${100+r*Math.sin(a*Math.PI/180)}`;
const arc=(a:number,b:number,r:number)=>`M${p(a,r)} A${r} ${r} 0 0 1 ${p(b,r)}`;
const wedge=(a:number,b:number,r:number)=>`M${p(a,30)} L${p(a,r)} A${r} ${r} 0 0 1 ${p(b,r)} L${p(b,30)} A30 30 0 0 0 ${p(a,30)}Z`;
export function SkillCircle({skills}:{skills:Model<'Skill'>[]}) {
 const assessed=skills.filter(s=>s.score!==null);const avg=assessed.length?Math.round(assessed.reduce((a,s)=>a+(s.score||0),0)/assessed.length):null;
 return <svg viewBox="0 0 200 200" width="264" height="264" className="scirc" role="img" aria-label={`Skill circle: ${assessed.length} of ${skills.length} assessed. ${avg===null?'No scores yet.':`Average ${avg}.`}`}>
  {skills.map((s,i)=>{const a=-90+i*360/skills.length+1.8,b=-90+(i+1)*360/skills.length-1.8;return <g key={s.id}><title>{s.name}: {s.score??'not assessed'} · target {s.target}</title><path d={wedge(a,b,94)} fill="rgba(79,70,229,.06)" stroke="rgba(79,70,229,.28)" strokeDasharray={s.score===null?'3 3':undefined}/>{s.score!==null&&s.score>0&&<path d={wedge(a,b,30+64*s.score/100)} fill={s.score<s.target-25?'#f59e0b':'#6366f1'} opacity={s.estimate?.55:.95}/>}<path d={arc(a+1,b-1,30+64*s.target/100)} fill="none" stroke="#1e1b4b" strokeWidth="2.2" opacity=".8"/></g>})}
  <circle cx="100" cy="100" r="27" fill="white" stroke="rgba(30,32,80,.1)"/><text x="100" y="104" textAnchor="middle" fontSize={avg===null?12:20} fontWeight="600">{avg??'New'}</text>{avg!==null&&<text x="100" y="116" textAnchor="middle" fontSize="7.5" fill="#71717a">average</text>}
 </svg>;
}
