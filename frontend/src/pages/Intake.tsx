import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router';
import { api } from '../api/client';
import { useApp } from '../store';
import { Shell } from '../components/Shell';
import { SourceManager } from '../components/SourceManager';
import { Badge, Button, ErrorNotice, Icon } from '../components/ui';
export const domains:Record<string,{name:string;tag:string}>={infra:{name:'Infra',tag:'Linux, servers and networking'},hw:{name:'Hardware',tag:'Circuits and embedded C'},sw:{name:'Software',tag:'Web dev and algorithms'},comm:{name:'Communication',tag:'Behavioral stories and explaining your work'}};
export function IntakePage(){
 const {intake,setIntake,setPlan}=useApp(); const nav=useNavigate();const [consent,setConsent]=useState(false);
 const mutation=useMutation({mutationFn:()=>api.createPlan(intake),onSuccess:p=>{setPlan(p.id);nav('/plan');}});
 const toggle=(key:'companies'|'struggles',v:string)=>setIntake({[key]:intake[key].includes(v)?intake[key].filter(x=>x!==v):[...intake[key],v]});
 const chips=(key:'companies'|'struggles',all:string[])=>all.map(v=><button type="button" className={`ochip ${intake[key].includes(v)?'on':''}`} aria-pressed={intake[key].includes(v)} key={v} onClick={()=>toggle(key,v)}>{v}</button>);
 const text=[intake.question,...intake.struggles].join(' ').toLowerCase();
 const matches:Record<string,boolean>={infra:/linux|server|502|network|pi/.test(text),hw:/circuit|power|embedded/.test(text),sw:/system design|api|algorithm/.test(text),comm:/behavioral|conflict|story/.test(text)};
 return <Shell><main className="page"><div className="wrap"><div className="obhead"><Badge>Set up · 1 minute</Badge><h1>Tell us where you're headed.</h1><p className="sub">PrepCrew builds your prep plan from your target and from the questions that tripped you up.</p></div><div className="obgrid"><form className="card obform" onSubmit={e=>{e.preventDefault();mutation.mutate();}}><div className="cb">
 <div className="osec"><div className="onum">1</div><div className="obox"><label htmlFor="role">What are you aiming for?</label><input id="role" required value={intake.role} onChange={e=>setIntake({role:e.target.value})} placeholder="e.g. Embedded SWE, backend engineer"/><div className="olab">Target companies</div><div className="ochips">{chips('companies',['NVIDIA','Tesla','Apple','Qualcomm','SpaceX','Texas Instruments','Anduril'])}</div></div></div>
 <div className="osec"><div className="onum">2</div><div className="obox"><label>Where have you struggled before?</label><div className="ochips">{chips('struggles',['Debugging under pressure','Linux & servers','Networking','Circuits & power','Embedded C','Algorithms','System design','Behavioral'])}</div></div></div>
 <div className="osec"><div className="onum">3</div><div className="obox"><label htmlFor="question">A question that got you</label><textarea id="question" rows={4} value={intake.question} onChange={e=>setIntake({question:e.target.value})} placeholder="Paste a question from a failed interview, or describe where you froze."/><div className="ofoot"><Button type="button" variant="ghost" size="sm" onClick={()=>setIntake({question:''})}>Clear</Button><input aria-label="Resume or GitHub link" placeholder="Resume or GitHub link (optional)" value={intake.link} onChange={e=>setIntake({link:e.target.value})}/></div></div></div>
 <SourceManager userId={intake.user_id} selected={intake.source_ids||[]} onSelect={source_ids=>setIntake({source_ids})} consent={consent}/>
 <label className="consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/> Save my answers and session transcript for this practice.</label><div className="row intake-footer"><span className="fine">Your plan is saved to your workspace.</span><Button size="lg" disabled={!consent||mutation.isPending}>{mutation.isPending?'Building your plan…':'Build my plan'}<Icon/></Button></div><ErrorNotice error={mutation.error}/></div></form>
 <aside className="card obprev"><div className="ch"><div><h3>What PrepCrew picks up</h3><p>Updates as you type</p></div></div><div className="cb">{Object.entries(domains).sort(([a],[b])=>Number(matches[b])-Number(matches[a])).map(([id,d],i)=><div className={`pk ${matches[id]?'hot':''}`} key={id}><span className="pkic"><Icon name={id}/></span><div><b>{d.name}</b> {i===0&&matches[id]&&<Badge tone="acc">Start here</Badge>}<small>{matches[id]?`Your answers point to ${d.tag.toLowerCase()}.`:'No signal yet. Added as a lighter track.'}</small></div></div>)}<p className="fine top-gap">Every domain gets a skill circle. Your first assessment lights up the wedges.</p></div></aside></div></div></main></Shell>;
}
