import type { components } from './types';
import { schemas } from './schemas';
import { z } from 'zod';
export type Model<K extends keyof components['schemas']> = components['schemas'][K];
export type Event = Model<'Event'>;
export type Stroke = Model<'Stroke'>;
export type Annotation = Model<'Annotation'>;
export type Intake = Model<'Intake'>;
export type Plan = Model<'Plan'>;
export type Session = Model<'Session'>;
export const API = (import.meta.env.VITE_API_URL || '').replace(/\/$/,'');
let accountEpoch=0;
const responseEpoch=new WeakMap<Response,number>();
export function invalidateAccountRequests(){++accountEpoch;}
export async function apiJson(response:Response):Promise<unknown>{
  const value:unknown=await response.json();
  if(responseEpoch.get(response)!==accountEpoch)throw new Error('The account changed. Reopen this view.');
  return value;
}
export async function apiFetch(path:string,init:RequestInit={}) {
  const epoch=accountEpoch;
  const headers=new Headers(init.headers);
  if(init.method&& !['GET','HEAD','OPTIONS'].includes(init.method))headers.set('X-PrepCrew-Request','1');
  const response=await fetch(`${API}/api/v2${path}`,{...init,headers,credentials:'include'});
  if(epoch!==accountEpoch)throw new Error('The account changed. Reopen this view.');
  responseEpoch.set(response,epoch);
  if(response.status===401&&!path.startsWith('/auth/'))window.dispatchEvent(new Event('prepcrew-auth-expired'));
  return response;
}
async function request<K extends keyof components['schemas']>(name: K, path: string, body?: unknown, input?: string): Promise<Model<K>> {
  if (input) schemas[input].parse(body);
  const response = await apiFetch(path,{method:body===undefined?'GET':'POST',headers:body===undefined?undefined:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  if (!response.ok) {
    const value: unknown = await apiJson(response).catch(()=>null);
    const error=z.object({detail:z.string()}).safeParse(value);
    throw new Error(error.success?error.data.detail:`The server returned ${response.status}. Your work has not been discarded.`);
  }
  return schemas[name].parse(await apiJson(response)) as Model<K>;
}
export const api = {
  auth:()=>request('AuthState','/auth/me'),
  login:(email:string,password:string)=>request('AuthState','/auth/login',{email,password},'Credentials'),
  register:(name:string,email:string,password:string)=>request('AuthState','/auth/register',{name,email,password},'Registration'),
  logout:()=>request('AuthState','/auth/logout',{}),
  history:(before?:string)=>request('History',`/history${before?'?before='+encodeURIComponent(before):''}`),
  health:()=>request('Health','/health'),
  sources:(user_id:string)=>request('SourceList',`/users/${encodeURIComponent(user_id)}/sources`),
  source:(id:string)=>request('SourceDocument',`/sources/${id}`),
  createSource:(body:Model<'SourceInput'>)=>request('SourceDocument','/sources',body,'SourceInput'),
  githubSource:(user_id:string,url:string)=>request('SourceDocument','/sources/github',{user_id,url},'SourceLinkInput'),
  extractSource:(id:string)=>request('WorkItem',`/sources/${id}/extract`,{}),
  confirmSource:(id:string,fact_indices:number[])=>request('SourceDocument',`/sources/${id}/confirm`,{fact_indices},'SourceConfirmation'),
  job:(id:string)=>request('WorkItem',`/jobs/${id}`),
  uploadSource:async(user_id:string,kind:Model<'SourceInput'>['kind'],file:File):Promise<Model<'SourceDocument'>>=>{
    const params=new URLSearchParams({user_id,kind:kind||'notes',title:file.name.slice(0,160)});
    const response=await apiFetch(`/sources/upload?${params}`,{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream'},body:file});
    if(!response.ok){const value:unknown=await apiJson(response).catch(()=>null);const error=z.object({detail:z.string()}).safeParse(value);throw new Error(error.success?error.data.detail:'Could not import this file.');}
    return schemas.SourceDocument.parse(await apiJson(response)) as Model<'SourceDocument'>;
  },
  plan:(id:string)=>request('Plan',`/plans/${id}`),
  createPlan:(body:Intake)=>request('Plan','/plans',body,'Intake'),
  createPlanJob:(body:Intake)=>request('WorkItem','/plans/jobs',body,'Intake'),
  start:(track_id:string)=>request('Session','/sessions',{track_id,consent:true},'Start'),
  session:(id:string)=>request('Session',`/sessions/${id}`),
  lab:(id:string,body:Model<'LabAction'>)=>request('TurnResult',`/sessions/${id}/lab`,body,'LabAction'),
  append:(id:string,body:Model<'EventInput'>)=>request('Event',`/sessions/${id}/events`,body,'EventInput'),
  turn:(id:string,body:Model<'TurnInput'>)=>request('TurnResult',`/sessions/${id}/turns`,body,'TurnInput'),
  board:(id:string,body:Model<'BoardInput'>)=>request('BoardResult',`/sessions/${id}/board`,body,'BoardInput'),
  boardElements:async(id:string,body:Model<'BoardElementsInput'>):Promise<Event[]>=>{
    schemas.BoardElementsInput.parse(body);
    const response=await apiFetch(`/sessions/${id}/board/elements`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if(!response.ok){const value:unknown=await apiJson(response).catch(()=>null);const error=z.object({detail:z.string()}).safeParse(value);throw new Error(error.success?error.data.detail:`The server returned ${response.status}. Your drawing is still on this device.`);}
    return z.array(schemas.Event).parse(await apiJson(response)) as Event[];
  },
  end:(id:string)=>request('Report',`/sessions/${id}/end`,{}),
  pause:(id:string,paused:boolean)=>request('Session',`/sessions/${id}/pause`,{paused},'PauseInput'),
  hint:(id:string)=>request('Event',`/sessions/${id}/hint`,{}),
  quit:(id:string,body:Model<'QuitInput'>)=>request('QuitResult',`/sessions/${id}/quit`,body,'QuitInput'),
  report:(id:string)=>request('Report',`/sessions/${id}/report`),
  metrics:(id:string)=>request('Metrics',`/sessions/${id}/metrics`),
  lesson:(id:string)=>request('Lesson',`/sessions/${id}/lesson`),
  generateLesson:(id:string)=>request('WorkItem',`/sessions/${id}/lesson/jobs`,{}),
  lessonJob:async(id:string):Promise<Model<'WorkItem'>|null>=>{
    const response=await apiFetch(`/sessions/${id}/lesson/jobs`);
    if(!response.ok)throw new Error('Could not load generation progress. Your evidence is saved.');
    return z.union([schemas.WorkItem,z.null()]).parse(await apiJson(response)) as Model<'WorkItem'>|null;
  },
  retryJob:(id:string)=>request('WorkItem',`/jobs/${id}/retry`,{}),
  cancelJob:(id:string)=>request('WorkItem',`/jobs/${id}/cancel`,{}),
  retest:(session_id:string)=>request('Session','/retests',{session_id},'RetestInput'),
  pair:(id:string)=>request('PairResult',`/sessions/${id}/pair`,{}),
};
export const eventMessage = z.object({type:z.literal('event'),event:schemas.Event});
export const pairMessage = z.union([eventMessage,
 z.object({type:z.literal('paired'),session_id:z.string(),device_id:z.string(),step:z.number().int()}),
 z.object({type:z.literal('state'),step:z.number().int(),drawable:z.boolean()}),
 z.object({type:z.literal('ack'),ids:z.array(z.string()),seq:z.number().int(),batch:z.string().optional()}),
 z.object({type:z.literal('review'),review:z.union([schemas.BoardResult,z.null()])}),
 z.object({type:z.literal('error'),message:z.string(),batch:z.string().optional()})]);
export function socketUrl(path:string) { const url=new URL(API||location.origin); url.protocol=url.protocol==='https:'?'wss:':'ws:'; url.pathname=path.split('?')[0]; url.search=path.split('?')[1]||''; return url.toString(); }
