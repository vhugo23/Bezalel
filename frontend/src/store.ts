import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { Intake } from './api/client';
interface State { intake:Intake; planId:string|null; voice:boolean; setIntake:(p:Partial<Intake>)=>void; setPlan:(id:string)=>void; toggleVoice:()=>void; }
export const useApp = create<State>()(persist((set)=>({
  intake:{user_id:crypto.randomUUID(),name:'Joshua',role:'Embedded SWE',companies:['NVIDIA','Tesla'],struggles:['Debugging under pressure','Linux & servers'],question:'Our web server on a Raspberry Pi is slow and sometimes returns 502. How would you track it down? I froze and started guessing.',link:''},
  planId:null,voice:false,
  setIntake:(p)=>set(s=>({intake:{...s.intake,...p}})),setPlan:(planId)=>set({planId}),toggleVoice:()=>set(s=>({voice:!s.voice})),
}),{name:'prepcrew-profile-v2',storage:createJSONStorage(()=>localStorage)}));

interface LiveState { mic:'idle'|'recording'|'transcribing'; setMic:(mic:LiveState['mic'])=>void; }
export const useLive = create<LiveState>((set)=>({mic:'idle',setMic:(mic)=>set({mic})}));
