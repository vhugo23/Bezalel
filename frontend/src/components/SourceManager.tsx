import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router';
import { z } from 'zod';
import { api, type Model } from '../api/client';
import { Badge, Button, ErrorNotice } from './ui';

const factsSchema=z.array(z.object({category:z.string(),quote:z.string(),start:z.number(),end:z.number()}));

export function SourceManager({userId,selected,onSelect,consent}:{userId:string;selected:string[];onSelect:(ids:string[])=>void;consent:boolean}){
 const cache=useQueryClient();const [kind,setKind]=useState<Model<'SourceInput'>['kind']>('resume');
 const [text,setText]=useState('');const [title,setTitle]=useState('');const [url,setUrl]=useState('');
 const [opened,setOpened]=useState<string|null>(null);const [chosen,setChosen]=useState<number[]>([]);const [jobId,setJobId]=useState<string|null>(null);
 const list=useQuery({queryKey:['sources',userId],queryFn:()=>api.sources(userId)});
 const source=useQuery({queryKey:['source',opened],queryFn:()=>api.source(opened!),enabled:!!opened});
 const job=useQuery({queryKey:['job',jobId],queryFn:()=>api.job(jobId!),enabled:!!jobId,refetchInterval:q=>['queued','running'].includes(q.state.data?.status||'')?700:false});
 const saved=(doc:Model<'SourceDocument'>)=>{void cache.invalidateQueries({queryKey:['sources',userId]});onSelect([...new Set([...selected,doc.id])].slice(0,10));setOpened(doc.id);setChosen([]);};
 const paste=useMutation({mutationFn:()=>api.createSource({user_id:userId,kind,title:title.trim()||'Pasted source',body:text}),onSuccess:doc=>{saved(doc);setText('');setTitle('');}});
 const upload=useMutation({mutationFn:(file:File)=>api.uploadSource(userId,kind,file),onSuccess:saved});
 const github=useMutation({mutationFn:()=>api.githubSource(userId,url),onSuccess:doc=>{saved(doc);setUrl('');}});
 const extract=useMutation({mutationFn:()=>api.extractSource(opened!),onSuccess:job=>{setJobId(job.id);cache.setQueryData(['job',job.id],job);}});
 const confirm=useMutation({mutationFn:()=>api.confirmSource(opened!,chosen),onSuccess:doc=>{cache.setQueryData(['source',opened],doc);void cache.invalidateQueries({queryKey:['sources',userId]});}});
 const retry=useMutation({mutationFn:()=>api.retryJob(jobId!),onSuccess:job=>cache.setQueryData(['job',job.id],job)});
 useEffect(()=>{if(job.data?.status==='succeeded'&&opened)void cache.invalidateQueries({queryKey:['source',opened]});},[job.data?.status,opened,cache]);
 useEffect(()=>{const saved=z.array(z.number().int().nonnegative()).safeParse(source.data?.extracted.selected_indices);if(saved.success)setChosen(saved.data);},[source.data]);
 const parsed=factsSchema.safeParse(source.data?.extracted.facts);const facts=parsed.success?parsed.data:[];
 const busy=paste.isPending||upload.isPending||github.isPending;
 const posting=selected.find(id=>list.data?.sources.some(doc=>doc.id===id&&doc.kind==='job_posting'));
 return <details className="source-manager"><summary>Add context <span className="fine">Resume, project README or job description</span></summary><div className="top-gap">
  <p className="fine">Optional. Add text you want used for practice. Public GitHub imports read the README only. Scanned PDFs need text pasted here.</p>
  <label htmlFor="source-kind">Source type</label><select id="source-kind" value={kind} onChange={e=>setKind(e.target.value as Model<'SourceInput'>['kind'])}><option value="resume">Resume</option><option value="job_posting">Job description</option><option value="repo">Project / repository</option><option value="notes">Notes</option></select>
  <input aria-label="Source title" placeholder="Title (optional)" value={title} onChange={e=>setTitle(e.target.value)} maxLength={160}/>
  <textarea aria-label="Source text" placeholder="Paste relevant text" rows={4} maxLength={60000} value={text} onChange={e=>setText(e.target.value)}/>
  <div className="row"><Button type="button" variant="outline" size="sm" disabled={!consent||busy||text.trim().length<10} onClick={()=>paste.mutate()}>Save source text</Button><label className="fine">Upload PDF, TXT or Markdown<input aria-label="Upload source file" type="file" accept=".pdf,.txt,.md" disabled={!consent||busy} onChange={e=>{const file=e.target.files?.[0];if(file)upload.mutate(file);e.target.value='';}}/></label></div>
  <div className="row top-gap"><input aria-label="Public GitHub repository URL" placeholder="https://github.com/owner/repo" value={url} onChange={e=>setUrl(e.target.value)}/><Button type="button" variant="outline" size="sm" disabled={!consent||busy||!url.trim()} onClick={()=>github.mutate()}>Import README</Button></div>
  {!consent&&<p className="fine">Check the save-consent box below to add context.</p>}
  <ErrorNotice error={list.error||paste.error||upload.error||github.error||source.error||extract.error||confirm.error||retry.error||job.error}/>
  {list.data?.sources.map(doc=><div className="source-row" key={doc.id}><label><input type="checkbox" checked={selected.includes(doc.id)} disabled={!selected.includes(doc.id)&&selected.length>=10} onChange={()=>onSelect(selected.includes(doc.id)?selected.filter(id=>id!==doc.id):[...selected,doc.id])}/>{doc.title}</label><Badge>{doc.kind==='job_posting'?'Job description':doc.kind}</Badge>{doc.kind==='resume'&&<Link className="text-button" to={`/resume?source=${encodeURIComponent(doc.id)}${posting?`&job=${encodeURIComponent(posting)}`:''}`}>{posting?'Tailor to this job':'Check for ATS'}</Link>}<Button type="button" variant="ghost" size="sm" onClick={()=>{setOpened(doc.id);setChosen([]);setJobId(null);}}>Review source</Button></div>)}
  {source.data&&<div className="source-preview"><b>{source.data.title}</b><details><summary>View saved text</summary><pre>{source.data.body}</pre></details>
   <p className="fine">Excerpts help prepare practice prompts. They do not establish your skill level.</p>
   {['queued','running'].includes(job.data?.status||'')?<p role="status">{job.data?.stage}</p>:job.data?.status==='failed'?<><p className="fine">{job.data.error}</p><Button type="button" size="sm" disabled={retry.isPending||job.data.attempts>=3} onClick={()=>retry.mutate()}>Retry extraction</Button></>:<Button type="button" variant="outline" size="sm" disabled={extract.isPending} onClick={()=>extract.mutate()}>Find useful excerpts</Button>}
   {facts.length>0&&<><Badge>{source.data.extracted.provider==='recorded'?'Recorded excerpt selection':'AI-selected excerpts'}</Badge>{facts.map((fact,i)=><label className="source-fact" key={i}><input type="checkbox" checked={chosen.includes(i)} onChange={()=>setChosen(chosen.includes(i)?chosen.filter(n=>n!==i):[...chosen,i])}/><span><small>{fact.category}</small><q>{fact.quote}</q></span></label>)}<Button type="button" size="sm" disabled={confirm.isPending} onClick={()=>confirm.mutate()}>Confirm selected excerpts</Button>{source.data.extracted.confirmed===true&&<p className="fine">Selection saved. You can change it above.</p>}</>}
  </div>}
 </div></details>;
}
