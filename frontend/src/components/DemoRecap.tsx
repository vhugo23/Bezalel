import { z } from 'zod';
import { apiFetch, apiJson } from '../api/client';

export const recapSchema=z.object({scripted:z.literal(true),weakpoints:z.array(z.string()),lesson:z.object({title:z.string(),body:z.string(),practice:z.string()}),retest_prompt:z.string()});
export async function demoRequest(sid:string,action:string,body:unknown){
 const response=await apiFetch(`/sessions/${sid}/demo/${action}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const value=await apiJson(response);
 if(!response.ok){const error=z.object({detail:z.string()}).safeParse(value);throw new Error(error.success?error.data.detail:'Demo playback could not save its next action. Retry to continue.');}
 return value;
}
export function DemoRecap({recap}:{recap:z.infer<typeof recapSchema>}){
 return <><h3>Places to improve</h3><ul>{recap.weakpoints.map(point=><li key={point}>{point}</li>)}</ul><h3>{recap.lesson.title}</h3><p>{recap.lesson.body}</p><p><b>Practise:</b> {recap.lesson.practice}</p><h3>Next attempt</h3><p>{recap.retest_prompt}</p></>;
}
