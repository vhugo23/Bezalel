import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { Intake } from './api/client';
import { randomId } from './lib/ids';
interface State { accountId:string|null; intake:Intake; planId:string|null; planJobId:string|null; voice:boolean; bindAccount:(id:string|null,name?:string)=>void; setIntake:(p:Partial<Intake>)=>void; setPlan:(id:string)=>void; setPlanJob:(id:string|null)=>void; toggleVoice:()=>void; }
const blankIntake=(id:string,name=''):Intake=>({user_id:id,name,role:'',companies:[],struggles:[],question:'',link:'',source_ids:[]});
export const useApp = create<State>()(persist((set)=>({
  intake:{user_id:randomId(),name:'Joshua',role:'Embedded SWE',companies:['NVIDIA','Tesla'],struggles:['Debugging under pressure','Linux & servers'],question:'Our web server on a Raspberry Pi is slow and sometimes returns 502. How would you track it down? I froze and started guessing.',link:''},
  accountId:null,planId:null,planJobId:null,voice:false,
  bindAccount:(id,name)=>set(s=>s.accountId===id&&id!==null?{}:{accountId:id,intake:blankIntake(id||randomId(),name),planId:null,planJobId:null,voice:false}),
  setIntake:(p)=>set(s=>({intake:{...s.intake,...p},planJobId:null})),setPlan:(planId)=>set({planId,planJobId:null}),setPlanJob:(planJobId)=>set({planJobId}),toggleVoice:()=>set(s=>({voice:!s.voice})),
}),{name:'prepcrew-profile-v2',storage:createJSONStorage(()=>localStorage)}));

interface LiveState { mic:'idle'|'recording'|'transcribing'; setMic:(mic:LiveState['mic'])=>void; }
export const useLive = create<LiveState>((set)=>({mic:'idle',setMic:(mic)=>set({mic})}));
