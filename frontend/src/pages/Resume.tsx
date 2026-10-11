import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router';
import { z } from 'zod';
import { api, type Model } from '../api/client';
import { useApp } from '../store';
import { Shell } from '../components/Shell';
import { Badge, Button, ErrorNotice, Icon } from '../components/ui';

type Doc=Model<'SourceDocument'>;type Review=Model<'AtsReview'>;type Kind='resume'|'job_posting';
const requirementsSchema=z.array(z.object({quote:z.string(),term:z.string(),level:z.enum(['required','preferred'])}));
const revisionSchema=z.object({format:z.literal('ats_revision')});
const CATEGORY:Record<Model<'AtsCategoryResult'>['id'],string>={format:'Format',sections:'Sections',keywords:'Keywords',impact:'Impact',clarity:'Clarity'};
const COVERAGE:Record<Model<'AtsCoverage'>['status'],{label:string;tone:string}>={found:{label:'Keyword found',tone:'ok'},evidence:{label:'Shown in other words',tone:'acc'},missing:{label:'Not on your resume',tone:'warn'}};
const active=(status?:string)=>status==='queued'||status==='running';
const count=(n:number,word:string)=>`${n} ${word}${n===1?'':'s'}`;
const fileName=(title:string)=>title.replace(/\.(pdf|txt|md)\b/gi,'').replace(/[^\w-]+/g,'-').replace(/^-+|-+$/g,'')||'resume';
function download(blob:Blob,name:string){const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=name;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}

// One queued work item: polled while it runs, with retry and cancel. Asking twice returns the same item.
function useWork(){
 const cache=useQueryClient();const [id,setId]=useState<string|null>(null);
 const job=useQuery({queryKey:['job',id],queryFn:()=>api.job(id!),enabled:!!id,refetchInterval:q=>active(q.state.data?.status)?700:false});
 const track=(item:Model<'WorkItem'>)=>{cache.setQueryData(['job',item.id],item);setId(item.id);};
 const retry=useMutation({mutationFn:()=>api.retryJob(id!),onSuccess:track});
 const cancel=useMutation({mutationFn:()=>api.cancelJob(id!),onSuccess:track});
 return {id,item:id?job.data:undefined,track,retry,cancel,error:job.error||retry.error||cancel.error};
}
function WorkStatus({work,cancellable=false}:{work:ReturnType<typeof useWork>;cancellable?:boolean}){
 const item=work.item;if(!item||item.status==='succeeded')return null;
 if(active(item.status))return <div className="ats-work"><p role="status"><span className="spin" aria-hidden="true"/>{item.stage}</p>{cancellable&&<Button type="button" variant="outline" size="sm" disabled={work.cancel.isPending} onClick={()=>work.cancel.mutate()}>Cancel</Button>}</div>;
 return <div className="ats-work">{item.status==='cancelled'?<p className="fine">Cancelled. Nothing was changed.</p>:<p className="error-notice" role="alert">{item.error||'This did not finish.'}</p>}<Button type="button" size="sm" disabled={work.retry.isPending||item.attempts>=3} onClick={()=>work.retry.mutate()}>Retry</Button>{item.attempts>=3&&<span className="fine">Attempt limit reached.</span>}</div>;
}

function SourcePicker({userId,kind,docs,selected,onSelect,onAdded}:{userId:string;kind:Kind;docs:Doc[];selected:string|null;onSelect:(id:string)=>void;onAdded:(doc:Doc)=>void}){
 const noun=kind==='resume'?'resume':'job posting';const Noun=kind==='resume'?'Resume':'Job posting';
 const [open,setOpen]=useState(false);const [consent,setConsent]=useState(false);const [title,setTitle]=useState('');const [text,setText]=useState('');
 const saved=(doc:Doc)=>{onAdded(doc);setText('');setTitle('');setConsent(false);setOpen(false);};
 const paste=useMutation({mutationFn:()=>api.createSource({user_id:userId,kind,title:title.trim()||`Pasted ${noun}`,body:text}),onSuccess:saved});
 const upload=useMutation({mutationFn:(file:File)=>api.uploadSource(userId,kind,file),onSuccess:saved});
 const busy=paste.isPending||upload.isPending;
 return <>
  {docs.length>0?<fieldset className="ats-pick"><legend className="fine">Choose a {noun}</legend>{docs.map(doc=><label key={doc.id}><input type="radio" name={`ats-${kind}`} checked={doc.id===selected} onChange={()=>onSelect(doc.id)}/><span>{doc.title}</span>{revisionSchema.safeParse(doc.extracted.origin).success&&<Badge tone="acc">Revised</Badge>}<time dateTime={doc.created_at}>{new Date(doc.created_at).toLocaleDateString()}</time></label>)}</fieldset>:<p className="fine">No {noun} saved yet. Add one below.</p>}
  {docs.length>0&&<Button type="button" variant="ghost" size="sm" aria-expanded={open} onClick={()=>setOpen(!open)}>{open?'Close':`Add a ${noun}`}</Button>}
  {(open||docs.length===0)&&<div className="ats-add">
   <label className="consent"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/> Save this document to my workspace.</label>
   <input aria-label={`${Noun} title`} placeholder="Title (optional)" value={title} onChange={e=>setTitle(e.target.value)} maxLength={160}/>
   <textarea aria-label={`${Noun} text`} placeholder={`Paste your ${noun} text`} rows={5} maxLength={60000} value={text} onChange={e=>setText(e.target.value)}/>
   <div className="row"><Button type="button" variant="outline" size="sm" disabled={!consent||busy||text.trim().length<10} onClick={()=>paste.mutate()}>Save {noun} text</Button><label className="fine">Upload PDF, TXT or Markdown<input aria-label={`Upload ${noun} file`} type="file" accept=".pdf,.txt,.md" disabled={!consent||busy} onChange={e=>{const file=e.target.files?.[0];if(file)upload.mutate(file);e.target.value='';}}/></label></div>
   {!consent&&<p className="fine">Tick the box above to add a {noun}.</p>}
   <ErrorNotice error={paste.error||upload.error}/>
  </div>}
 </>;
}

function ReviewResult({review}:{review:Review}){
 // The number is only ever review.score. A recorded review has none, and none is estimated here.
 const score=review.provider!=='recorded'&&typeof review.score==='number'?review.score:null;
 return <div className="ats-block"><h3>Result</h3>
  {score===null?<p className="focus">Recorded example. Live mode is needed for a score.</p>:<p className="ats-score"><b>{score}</b><span>/ 100</span><Badge tone="acc">AI estimate · no real ATS was run</Badge></p>}
  {review.categories.length>0&&<div className="ats-cats">{review.categories.map(c=><article className="ats-cat" key={c.id}><header><b>{CATEGORY[c.id]}</b><span>{c.rating} / 4</span></header><div className="progress" aria-hidden="true"><i style={{width:`${c.rating*25}%`}}/></div>{c.findings.length?<ul>{c.findings.map((f,i)=><li key={i}>{f.issue}{f.quote&&<q>{f.quote}</q>}</li>)}</ul>:<p className="fine">No issues noted.</p>}</article>)}</div>}
  <dl className="ats-facts"><div><dt>Word count</dt><dd>{review.facts.words}</dd></div><div><dt>Email</dt><dd>{review.facts.email?'Found':'Not found'}</dd></div><div><dt>Phone</dt><dd>{review.facts.phone?'Found':'Not found'}</dd></div><div><dt>Sections detected</dt><dd>{review.facts.sections.join(', ')||'None'}</dd></div></dl>
  {score!==null&&<p className="fine">The score is computed from the category ratings. The weights are hand-picked and have not been checked against a real applicant tracking system.</p>}
 </div>;
}

// A missing requirement is never offered as a change: the row has text and a practice link only.
function Coverage({rows}:{rows:Model<'AtsCoverage'>[]}){
 return <div className="ats-block"><h3>Job requirements</h3><div className="ats-table"><table><thead><tr><th scope="col">Requirement</th><th scope="col">Level</th><th scope="col">Status</th></tr></thead><tbody>{rows.map((row,i)=><tr key={i}><td><q>{row.quote}</q></td><td>{row.level==='required'?'Required':'Preferred'}</td><td><Badge tone={COVERAGE[row.status].tone}>{COVERAGE[row.status].label}</Badge>{row.status==='evidence'&&row.resume_quote&&<q>{row.resume_quote}</q>}{row.status==='missing'&&<p><span className="fine">We will not add this to your resume.</span> <Link to="/plan">Practise this</Link></p>}</td></tr>)}</tbody></table></div></div>;
}

function Suggestions({review,pending,onApply}:{review:Review;pending:boolean;onApply:(ids:number[])=>void}){
 const [off,setOff]=useState<number[]>([]);const ticked=review.suggestions.filter(s=>!off.includes(s.id)).map(s=>s.id);
 return <div className="ats-block"><h3>Suggested changes</h3>
  {review.suggestions.length===0?<p className="fine">There are no suggested changes.</p>:<>
   <p className="fine">Each change replaces text that is already in your resume. Untick any you do not want.</p>
   {review.suggestions.map((s,i)=><article className="ats-sug" key={s.id}><div className="ats-sug-h"><label><input type="checkbox" checked={!off.includes(s.id)} onChange={()=>setOff(off.includes(s.id)?off.filter(id=>id!==s.id):[...off,s.id])}/>Change {i+1}</label><Badge tone="acc">AI generated</Badge><Badge>{CATEGORY[s.category]}</Badge></div><div className="ats-diff"><div className="before"><small>Original</small><del>{s.original}</del></div><div className="after"><small>Replacement</small><ins>{s.replacement}</ins></div></div><p className="fine">{s.reason}</p></article>)}
   <div className="row top-gap"><Button type="button" disabled={pending||ticked.length===0} onClick={()=>onApply(ticked)}>{pending?'Applying…':`Apply selected (${ticked.length})`}</Button><span className="fine">Creates a new revised resume.</span></div></>}
  {review.rejected>0&&<p className="fine top-gap">{review.rejected} {review.rejected===1?'suggestion was':'suggestions were'} discarded by our checks because they added a number or a skill your resume does not contain, or could not be matched to your text.</p>}
 </div>;
}

function Revised({doc,onCheck}:{doc:Doc;onCheck:()=>void}){
 const copy=useMutation({mutationFn:async()=>{try{await navigator.clipboard.writeText(doc.body);}catch{throw new Error('Could not copy. Select the text and copy it yourself.');}}});
 const pdf=useMutation({mutationFn:()=>api.resumePdf(doc.id),onSuccess:blob=>download(blob,`${fileName(doc.title)}.pdf`)});
 return <div className="ats-block ats-revised"><h3>Revised resume</h3><p className="fine">Your original resume is unchanged.</p>
  <textarea readOnly aria-label="Revised resume text" rows={14} value={doc.body}/>
  <div className="row"><Button type="button" variant="outline" size="sm" onClick={()=>copy.mutate()}>{copy.isSuccess?'Copied':'Copy'}</Button><Button type="button" variant="outline" size="sm" onClick={()=>download(new Blob([doc.body],{type:'text/markdown;charset=utf-8'}),`${fileName(doc.title)}.md`)}>Download .md</Button><Button type="button" variant="outline" size="sm" disabled={pdf.isPending} onClick={()=>pdf.mutate()}>{pdf.isPending?'Preparing PDF…':'Download PDF'}</Button><Button type="button" size="sm" onClick={onCheck}>Check this version<Icon/></Button></div>
  <ErrorNotice error={copy.error||pdf.error}/>
 </div>;
}

// One review of one resume, general or tailored to one posting. The caller keys it by both ids, so
// nothing here can outlive a change of selection.
function ReviewPanel({resumeId,jobId,label,auto,onAuto,onAdded,onCheck,children}:{resumeId:string;jobId?:string;label:string;auto:boolean;onAuto:()=>void;onAdded:(doc:Doc)=>void;onCheck:(doc:Doc)=>void;children?:ReactNode}){
 const cache=useQueryClient();const work=useWork();const fired=useRef(false);
 const review=useQuery({queryKey:['ats',resumeId,jobId??null],queryFn:()=>api.atsResult(resumeId,jobId)});
 const start=useMutation({mutationFn:()=>api.atsReview(resumeId,jobId),onSuccess:item=>{work.track(item);if(item.status==='succeeded')void cache.invalidateQueries({queryKey:['ats',resumeId,jobId??null]});}});
 const apply=useMutation({mutationFn:(suggestion_ids:number[])=>api.atsApply(resumeId,jobId?{job_id:jobId,suggestion_ids}:{suggestion_ids}),onSuccess:onAdded});
 const status=work.item?.status;const stuck=status==='failed'||status==='cancelled';const revised=apply.data;
 useEffect(()=>{if(status==='succeeded')void cache.invalidateQueries({queryKey:['ats',resumeId,jobId??null]});},[status,resumeId,jobId,cache]);
 const begin=start.mutate;
 useEffect(()=>{if(auto&&!fired.current){fired.current=true;begin();onAuto();}},[auto,begin,onAuto]);
 return <section className="ats-review" aria-label={jobId?'Tailored review':'General review'}>
  <div className="ats-offer">{children}{!active(status)&&!stuck&&<Button type="button" disabled={start.isPending} onClick={()=>start.mutate()}>{start.isPending?'Starting…':label}<Icon/></Button>}</div>
  <WorkStatus work={work} cancellable/>
  <ErrorNotice error={review.error||start.error||work.error||apply.error}/>
  {review.isLoading&&<p className="fine top-gap">Looking for a saved review…</p>}
  {review.data&&<><ReviewResult review={review.data}/>{jobId&&!!review.data.coverage?.length&&<Coverage rows={review.data.coverage}/>}<Suggestions review={review.data} pending={apply.isPending} onApply={ids=>apply.mutate(ids)}/></>}
  {revised&&<Revised doc={revised} onCheck={()=>onCheck(revised)}/>}
 </section>;
}

// A selected posting is scanned once if it has no requirements yet, then offered for tailoring.
function Tailor({posting,resumeId,auto,onAuto,onAdded,onCheck}:{posting:Doc;resumeId:string|null;auto:boolean;onAuto:()=>void;onAdded:(doc:Doc)=>void;onCheck:(doc:Doc)=>void}){
 const cache=useQueryClient();const work=useWork();const id=posting.id;
 const source=useQuery({queryKey:['source',id],queryFn:()=>api.source(id),placeholderData:posting});
 const scan=useMutation({mutationFn:()=>api.scanSource(id),onSuccess:item=>{work.track(item);if(item.status==='succeeded')void cache.invalidateQueries({queryKey:['source',id]});}});
 const parsed=requirementsSchema.safeParse(source.data?.extracted.requirements);const requirements=parsed.success?parsed.data:null;
 const status=work.item?.status;const unscanned=source.isSuccess&&!source.isFetching&&!requirements&&!work.id&&scan.isIdle;
 const begin=scan.mutate;
 useEffect(()=>{if(unscanned)begin();},[unscanned,begin]);
 useEffect(()=>{if(status==='succeeded')void cache.invalidateQueries({queryKey:['source',id]});},[status,id,cache]);
 const required=requirements?.filter(r=>r.level==='required').length||0;
 return <div className="ats-tailor"><ErrorNotice error={source.error||scan.error||work.error}/>
  {requirements?<p className="fine" role="status">{count(requirements.length,'requirement')} found ({required} required, {requirements.length-required} preferred)</p>
   :scan.isError?<Button type="button" variant="outline" size="sm" onClick={()=>scan.mutate()}>Scan again</Button>
   :work.item&&status!=='succeeded'?<WorkStatus work={work}/>
   :status==='succeeded'&&!source.isFetching?<p className="fine">The scan finished but no requirements were saved for this posting.</p>
   :!source.isError&&<div className="ats-work"><p role="status"><span className="spin" aria-hidden="true"/>{source.isFetching&&!work.id?'Opening the job posting…':'Scanning the job posting…'}</p></div>}
  {requirements&&(resumeId?<ReviewPanel key={`${resumeId}:${id}`} resumeId={resumeId} jobId={id} label="Tailor my resume" auto={auto} onAuto={onAuto} onAdded={onAdded} onCheck={onCheck}><h3>Tailor your resume for {posting.title}?</h3></ReviewPanel>:<p className="fine">Pick a resume above to tailor it.</p>)}
 </div>;
}

export function ResumePage(){
 const userId=useApp(s=>s.intake.user_id);const cache=useQueryClient();const [params,setParams]=useSearchParams();
 const [auto,setAuto]=useState<{resume:string;job:string|null}|null>(null);
 const list=useQuery({queryKey:['sources',userId],queryFn:()=>api.sources(userId)});
 const newest=(kind:Kind)=>(list.data?.sources||[]).filter(doc=>doc.kind===kind).sort((a,b)=>Date.parse(b.created_at)-Date.parse(a.created_at));
 const resumes=newest('resume');const postings=newest('job_posting');
 const resume=resumes.find(doc=>doc.id===params.get('source'))||null;const posting=postings.find(doc=>doc.id===params.get('job'))||null;
 const pick=(key:'source'|'job',id:string|null)=>setParams(prev=>{const next=new URLSearchParams(prev);if(id)next.set(key,id);else next.delete(key);return next;},{replace:true});
 const add=(doc:Doc)=>{cache.setQueryData(['source',doc.id],doc);cache.setQueryData<Model<'SourceList'>>(['sources',userId],old=>old&&{...old,sources:[doc,...old.sources.filter(d=>d.id!==doc.id)]});void cache.invalidateQueries({queryKey:['sources',userId]});};
 const check=(doc:Doc,job:string|null)=>{pick('source',doc.id);setAuto({resume:doc.id,job});};
 const fallback=resume?null:resumes[0]?.id||null;
 useEffect(()=>{if(fallback)setParams(prev=>{const next=new URLSearchParams(prev);next.set('source',fallback);return next;},{replace:true});},[fallback,setParams]);
 return <Shell><main className="page"><div className="wrap ats"><div className="hhead"><div><h1>Resume check</h1><p className="sub">An AI review of your resume's format, sections, keywords, impact and clarity. No real applicant tracking system is run.</p></div></div>
  <ErrorNotice error={list.error}/>
  <section className="card"><div className="ch"><div><h2>Your resume</h2><p>Pick the resume to check, or add one.</p></div></div><div className="cb">{list.isLoading?<p className="fine" role="status">Opening your documents…</p>:<SourcePicker userId={userId} kind="resume" docs={resumes} selected={resume?.id||null} onSelect={id=>pick('source',id)} onAdded={doc=>{add(doc);pick('source',doc.id);}}/>}</div></section>
  <section className="card top-gap"><div className="ch"><div><h2>Check my resume</h2><p>A general review, not tied to any job.</p></div></div><div className="cb">{resume?<ReviewPanel key={resume.id} resumeId={resume.id} label="Check my resume" auto={auto?.resume===resume.id&&auto.job===null} onAuto={()=>setAuto(null)} onAdded={add} onCheck={doc=>check(doc,null)}/>:<p className="fine">Pick or add a resume first.</p>}</div></section>
  <section className="card top-gap"><div className="ch"><div><h2>Tailor to a job</h2><p>Compare your resume with a job posting's requirements.</p></div>{posting&&<Button type="button" variant="ghost" size="sm" onClick={()=>pick('job',null)}>Clear selection</Button>}</div><div className="cb">{!list.isLoading&&<SourcePicker userId={userId} kind="job_posting" docs={postings} selected={posting?.id||null} onSelect={id=>pick('job',id)} onAdded={doc=>{add(doc);pick('job',doc.id);}}/>}
   {posting&&<Tailor key={posting.id} posting={posting} resumeId={resume?.id||null} auto={!!resume&&auto?.resume===resume.id&&auto.job===posting.id} onAuto={()=>setAuto(null)} onAdded={add} onCheck={doc=>check(doc,posting.id)}/>}</div></section>
 </div></main></Shell>;
}
