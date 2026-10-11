import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type Event, type Model } from '../api/client';
import { Shell } from '../components/Shell';
import { Badge, Button, ErrorNotice, Icon, Modal } from '../components/ui';

const names=['Requirements','Whiteboard','Trade-offs','Communication'];
const descriptions=['Did you scope before designing','What you drew and explained','Naming what you gave up','Clear, direct answers'];

export function FleetPage(){
 const {id=''}=useParams();const [evidence,setEvidence]=useState<Event[]|null>(null);const nav=useNavigate();const cache=useQueryClient();
 const report=useQuery({queryKey:['report',id],queryFn:()=>api.report(id),refetchInterval:q=>['graded','failed'].includes(q.state.data?.status||'')?false:800});
 const session=useQuery({queryKey:['session',id],queryFn:()=>api.session(id)});
 const metrics=useQuery({queryKey:['metrics',id],queryFn:()=>api.metrics(id),refetchInterval:report.data?.status==='graded'?false:1500});
 const retry=useMutation({mutationFn:()=>api.end(id),onSuccess:r=>{cache.setQueryData(['report',id],r);void cache.invalidateQueries({queryKey:['metrics',id]});}});
 const done=report.data?.status==='graded';
 const claims=(report.data?.claims||[]).map(c=>({...c,quotes:c.quotes||[]}));
 const verified=claims.filter(c=>c.check_status==='verified'),rejected=claims.filter(c=>c.check_status==='rejected');
 const gap=report.data?.next_gap;
 const scores=report.data?.scores||[];
 const [search]=useSearchParams();const evidenceSeq=Number(search.get('evidence'));
 useEffect(()=>{if(Number.isInteger(evidenceSeq)&&evidenceSeq>0&&session.data)setEvidence(session.data.events.filter(e=>e.seq===evidenceSeq));},[evidenceSeq,session.data]);
 const show=(claim:Model<'CheckedClaim'>)=>setEvidence(session.data?.events.filter(e=>claim.evidence_seq.includes(e.seq))||[]);
 return <Shell><main className="page"><div className="wrap">
  <div className="obhead"><Badge tone="acc">{done?'Session reviewed':'Grading'}</Badge><h1>Four evaluators, in parallel.</h1><p className="sub">Each reads the same session log. Claims pass reference checks and an independent model review before contributing to your scores.</p></div>
  <ErrorNotice error={report.error||session.error||retry.error}/>
  {(report.data?.partial||report.data?.status==='failed')&&<section className="card"><div className="cb"><h3>Your review needs another pass.</h3><p className="fine">Completed evaluators are saved. Retry resumes the unfinished work; partial results do not update your skill circles.</p><Button className="top-gap" disabled={retry.isPending||report.data?.status==='grading'} onClick={()=>retry.mutate()}>Retry review</Button></div></section>}
  <div className="fgrid">{names.map((name,i)=>{
   const run=report.data?.evaluators.find(r=>r.name===name);const checked=verified.filter(c=>c.evaluator===name);
   return <section className={`card fcard ${run?.status==='done'?'done':'run'}`} key={name}><div className="cb">
    <div className="fh"><b>{name}</b><Badge>{report.data?.demo?'Recorded':'Gemini'}</Badge></div><span className="fd">{descriptions[i]}</span>
    <div className="fst">{run?.status==='done'?<Icon name="check"/>:run?.status==='failed'?<span>!</span>:<span className="spin"/>}{run?.status==='done'?'Evidence checked':run?.status==='failed'?'Evaluation failed':'Reading the session log'}</div>
    {run?.status==='done'?<div className="fres"><div className="fsc">{checked.length}<span className="count-label"> supported</span></div><p>{checked.length?'Open a citation below to inspect the source event.':'No supported claims to include.'}</p></div>:run?.status==='failed'?<p className="fine top-gap">This evaluator did not finish. Its output is excluded.</p>:<div className="fbody"><i/><i/><i/></div>}
   </div></section>;
  })}</div>
  {!!scores.length&&<section className="card"><div className="ch"><div><h3>Your skill assessments</h3><p>Only supported, scored criteria update a circle</p></div><Badge>Practice rubric</Badge></div><div className="cb metrics-grid">{scores.map(score=><div className="stat" key={score.skill_id}><small>{score.name}</small><div className="v">{score.score}<small> / 100</small></div><small>{score.previous==null?'First assessment':`Previously ${score.previous} · ${(score.delta??0)>=0?'+':''}${score.delta??0}`}</small><div className="citations">{score.previous_session_id&&<Link to={`/fleet/${score.previous_session_id}`}>Previous evidence {score.previous_evidence_seq?.map(seq=>`#${seq}`).join(', ')}</Link>}{score.claim_ids.map(cid=>{const claim=verified.find(c=>c.id===cid);return claim?<button key={cid} onClick={()=>show(claim)}>Evidence {claim.evidence_seq.map(seq=>`#${seq}`).join(', ')}</button>:null;})}</div></div>)}</div></section>}
  <section className="card"><div className="ch"><div><h3>Evidence checker</h3><p>Every reference resolves to this session’s event log</p></div><Badge tone="ok">{verified.length} supported</Badge></div><div className="cb">
   {verified.length?verified.map(c=><div className="cr ok" key={c.id}><span className="spin"><Icon name="check"/></span><div><b>{c.text}</b><div className="ev">{c.evaluator} · {c.quotes.length?`“${c.quotes[0]}”`:'Candidate stroke recorded'}<div className="citations">{c.evidence_seq.map(seq=><button onClick={()=>show(c)} key={seq}>Event #{seq}</button>)}</div></div></div><Badge tone="ok">Supported</Badge></div>):<p className="fine">{done?'No candidate claims have sufficient evidence yet.':'Waiting for the evaluators…'}</p>}
   {rejected.map(c=><div className="cr bad" key={c.id}><span className="spin">×</span><div><b>Rejected proposal: “{c.text}”</b><div className="ev">{c.check_reason}. Excluded from your report and skill assessments.</div></div><Badge tone="bad">Rejected</Badge></div>)}
  </div></section>
  <p className="fine top-gap">{report.data?.demo?'Recorded evaluator fixtures demonstrate acceptance and rejection. They are not a live assessment of your ability.':'Exact references are checked in code; an independent model reviews interpretation and scoring. These practice rubrics still need human calibration.'}</p>
  <div className="below"><section className="card"><div className="ch"><div><h3>Session measurements</h3><p>Tiger Data · measured values only</p></div><Badge>{metrics.data?.hypertables.length||'—'} hypertables</Badge></div><div className="cb metrics-grid">{metrics.data?.rows.length?metrics.data.rows.map((r,i)=><div className="stat" key={i}><small>{String(r.name)}</small><div className="v">{Math.round(Number(r.p50))}<small> ms</small></div><small>p50 · {String(r.n)} sample(s)</small></div>):<p className="fine">No latency samples yet.</p>}<p className="fine">Continuous aggregates: {metrics.data?.aggregates.join(' · ')||'Loading…'}</p></div></section>
   <section className="card"><div className="ch"><h3>Keep the practice going</h3></div><div className="cb">{gap?<><p className="mut">Build a short lesson and a new retest around this supported gap.</p><div className="focus">{gap.text}<div className="citations">{gap.evidence_seq.map(seq=><button key={seq} onClick={()=>setEvidence(session.data?.events.filter(e=>e.seq===seq)||[])}>Event #{seq}</button>)}</div></div><Button asChild className="top-gap"><Link to={`/lesson/${id}`}>Open the lesson<Icon/></Link></Button></>:<p className="mut">{done?'No verified gap to turn into a lesson in this review. Your evidence is available above.':'Your next practice will follow the evidence from the completed review.'}</p>}</div></section>
  </div><div className="fbar"><span className="fine">{done?`${verified.length} supported · ${rejected.length} rejected`:'Evaluators are working…'}</span><span className="grow"/><Button variant="outline" onClick={()=>nav('/plan')}>See your skill circles<Icon/></Button></div>
 </div></main><Modal open={evidence!==null} onClose={()=>setEvidence(null)} title="Source evidence" description="Saved events from this session. Dana’s annotations are kept apart from candidate work.">{evidence?.map(e=><div className="evidence-item" key={e.seq}><Badge>Event #{e.seq}</Badge> <Badge>{e.actor} · {e.kind}</Badge><p>{String(e.payload.text||e.payload.label||'Candidate stroke')}</p><pre>{JSON.stringify(e.payload,null,2)}</pre></div>)}</Modal></Shell>;
}

export function LessonPage(){
 const {id=''}=useParams();const nav=useNavigate();const cache=useQueryClient();
 const query=useQuery({queryKey:['lesson',id],queryFn:()=>api.lesson(id),retry:false});
 const generate=useMutation({mutationFn:()=>api.generateLesson(id),onSuccess:lesson=>{cache.setQueryData(['lesson',id],lesson);void cache.invalidateQueries({queryKey:['plan']});}});
 const retest=useMutation({mutationFn:()=>api.retest(id),onSuccess:s=>nav(`/session/${s.id}`)});
 const lesson=query.data;
 return <Shell><main className="page"><div className="wrap lesson-wrap"><Badge tone="acc">Practice loop</Badge><h1 className="top-gap">{lesson?.title||'Your next practice'}</h1><p className="sub">A lesson and a new constraint, grounded in your session.</p><section className="card"><div className="cb lesson-body">
  {lesson?.id&&<Badge>Gemini · independently reviewed</Badge>}
  {lesson?.body?<><p style={{whiteSpace:'pre-line'}}>{lesson.body}</p><h2>Try it yourself.</h2><p style={{whiteSpace:'pre-line'}}>{lesson.practice}</p><p className="fine">The retest is a model-reviewed conceptual exercise. Its correctness is not deterministically proven.</p></>:<p>{generate.isPending?'Preparing your lesson and reviewing the new retest…':query.isPending?'Loading your evidence…':'Generate a short lesson and a changed system-design prompt for the verified gap below.'}</p>}
  {lesson&&<div className="focus">{lesson.reason}<div className="citations">{lesson.evidence_seq.map(seq=><Link key={seq} to={`/fleet/${id}?evidence=${seq}`}>Event #{seq}</Link>)}</div></div>}
  <ErrorNotice error={query.error||generate.error||retest.error}/>
  <div className="row lesson-actions"><Button variant="outline" asChild><Link to={`/fleet/${id}`}>Back to evidence</Link></Button>{lesson&&!lesson.id?<Button disabled={generate.isPending} onClick={()=>generate.mutate()}>{generate.isPending?'Reviewing…':'Generate my lesson'}<Icon/></Button>:lesson?.retest_ready?<Button disabled={retest.isPending} onClick={()=>retest.mutate()}>Start retest<Icon/></Button>:null}</div>
 </div></section></div></main></Shell>;
}
