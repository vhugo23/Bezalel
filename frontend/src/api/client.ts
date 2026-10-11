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
async function request<K extends keyof components['schemas']>(name: K, path: string, body?: unknown, input?: string): Promise<Model<K>> {
  if (input) schemas[input].parse(body);
  const response = await fetch(`${API}/api/v2${path}`,{method:body===undefined?'GET':'POST',headers:body===undefined?undefined:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
  if (!response.ok) {
    const value: unknown = await response.json().catch(()=>null);
    const error=z.object({detail:z.string()}).safeParse(value);
    throw new Error(error.success?error.data.detail:`The server returned ${response.status}. Your work has not been discarded.`);
  }
  return schemas[name].parse(await response.json()) as Model<K>;
}
export const api = {
  health:()=>request('Health','/health'),
  plan:(id:string)=>request('Plan',`/plans/${id}`),
  createPlan:(body:Intake)=>request('Plan','/plans',body,'Intake'),
  start:(track_id:string)=>request('Session','/sessions',{track_id,consent:true},'Start'),
  session:(id:string)=>request('Session',`/sessions/${id}`),
  append:(id:string,body:Model<'EventInput'>)=>request('Event',`/sessions/${id}/events`,body,'EventInput'),
  turn:(id:string,body:Model<'TurnInput'>)=>request('TurnResult',`/sessions/${id}/turns`,body,'TurnInput'),
  board:(id:string,body:Model<'BoardInput'>)=>request('BoardResult',`/sessions/${id}/board`,body,'BoardInput'),
  end:(id:string)=>request('Report',`/sessions/${id}/end`,{}),
  pause:(id:string,paused:boolean)=>request('Session',`/sessions/${id}/pause`,{paused},'PauseInput'),
  hint:(id:string)=>request('Event',`/sessions/${id}/hint`,{}),
  report:(id:string)=>request('Report',`/sessions/${id}/report`),
  metrics:(id:string)=>request('Metrics',`/sessions/${id}/metrics`),
  lesson:(id:string)=>request('Lesson',`/sessions/${id}/lesson`),
  generateLesson:(id:string)=>request('Lesson',`/sessions/${id}/lesson`,{}),
  retest:(session_id:string)=>request('Session','/retests',{session_id},'RetestInput'),
  pair:(id:string)=>request('PairResult',`/sessions/${id}/pair`,{}),
};
export const eventMessage = z.object({type:z.literal('event'),event:schemas.Event});
export const pairMessage = z.union([eventMessage,z.object({type:z.literal('paired'),session_id:z.string()}),z.object({type:z.literal('error'),message:z.string()})]);
export function socketUrl(path:string) { const url=new URL(API||location.origin); url.protocol=url.protocol==='https:'?'wss:':'ws:'; url.pathname=path.split('?')[0]; url.search=path.split('?')[1]||''; return url.toString(); }
