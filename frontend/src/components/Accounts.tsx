import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Outlet } from 'react-router';
import { api, invalidateAccountRequests, type Model } from '../api/client';
import { useApp } from '../store';
import { Button, ErrorNotice, Icon } from './ui';

type State=Model<'AuthState'>;
type AuthContext={state:State|undefined;error:unknown;accept:(state:State)=>Promise<void>;refresh:()=>Promise<void>;logout:()=>Promise<void>};
const Context=createContext<AuthContext|null>(null);
export const useAuth=()=>useContext(Context);
const signal=()=>{try{localStorage.setItem('prepcrew-account-change',String(Date.now()));}catch{/* Account cookies still work without storage. */}};

export function AccountProvider({children}:{children:ReactNode}) {
 const cache=useQueryClient();const [state,setState]=useState<State>();const [error,setError]=useState<unknown>();
 const version=useRef(0);const activeId=useRef<string|null|undefined>(undefined);
 const transitioning=useRef(false);
 async function accept(next:State){
  const id=next.user?.id||null;
  if(next.enabled&&activeId.current===id){if(!transitioning.current)setState(next);return;}
  const revision=++version.current;
  if(next.enabled){
   activeId.current=id;transitioning.current=true;
   setState(undefined);invalidateAccountRequests();await cache.cancelQueries();cache.clear();
   if(revision!==version.current)return;
   const previous=useApp.getState();
   if(!previous.accountId&&(previous.planId||previous.planJobId)&&previous.intake.user_id!==id){
    // Keep only the operator's old workspace locator, never a transcript/draft.
    try{localStorage.setItem('prepcrew-legacy-workspace-id',previous.intake.user_id);}catch{/* Data remains on the server. */}
   }
   useApp.getState().bindAccount(id,next.user?.name);
   if(id&&!useApp.getState().planId){
    try{
     const history=await api.history();
     if(history.latest_plan_id){
      const plan=await api.plan(history.latest_plan_id);
      if(revision===version.current){useApp.getState().setIntake(plan.intake);useApp.getState().setPlan(plan.id);}
     }
    }catch(e){if(revision===version.current)setError(e);}
   }
  }
  if(revision===version.current){transitioning.current=false;setState(next);}
 }
 async function refresh(){
  const revision=version.current;
  try{const next=await api.auth();if(revision!==version.current)return;setError(undefined);await accept(next);}catch(e){if(revision===version.current)setError(e);}
 }
 async function logout(){try{const next=await api.logout();await accept(next);signal();}catch(e){setError(e);}}
 useEffect(()=>{
  void refresh();
  const expired=()=>{void accept({enabled:true,user:null});};
  const changed=(e:StorageEvent)=>{if(e.key==='prepcrew-account-change')void refresh();};
  const focus=()=>{void refresh();};
  window.addEventListener('prepcrew-auth-expired',expired);window.addEventListener('storage',changed);window.addEventListener('focus',focus);
  const timer=window.setInterval(()=>{void refresh();},60000);
  return()=>{++version.current;clearInterval(timer);window.removeEventListener('prepcrew-auth-expired',expired);window.removeEventListener('storage',changed);window.removeEventListener('focus',focus);};
 },[]);
 return <Context.Provider value={{state,error,accept,refresh,logout}}>{children}</Context.Provider>;
}

export function AccountWorkspace(){
 const auth=useAuth()!;
 if(!auth.state)return <main className="empty-state"><h1>Opening your workspace…</h1><ErrorNotice error={auth.error}/>{!!auth.error&&<Button onClick={()=>void auth.refresh()}>Retry connection</Button>}</main>;
 if(auth.state.enabled&&!auth.state.user)return <SignIn/>;
 return <Outlet/>;
}

export function SignIn(){
 const auth=useAuth()!;const [register,setRegister]=useState(false);const [name,setName]=useState('');const [email,setEmail]=useState('');const [password,setPassword]=useState('');const [busy,setBusy]=useState(false);const [error,setError]=useState<unknown>();
 return <main className="account-page"><a href="/plan" className="logo"><img src="/prepcrew.svg" width="28" height="28" alt="" aria-hidden="true" style={{display:'block',flexShrink:0}}/>PrepCrew</a><section className="card account-card"><span className="account-eyebrow">A little practice. A clearer next step.</span><h1>{register?'Make room to grow.':'Welcome back.'}</h1><p className="sub">Keep your plan, conversations and progress together.</p><form onSubmit={async e=>{e.preventDefault();setBusy(true);setError(undefined);try{const next=register?await api.register(name,email,password):await api.login(email,password);setPassword('');await auth.accept(next);signal();}catch(e){setError(e);}finally{setBusy(false);}}}>
 {register&&<label>Your name<input autoComplete="name" required maxLength={80} value={name} onChange={e=>setName(e.target.value)}/></label>}
 <label>Email<input type="email" autoComplete="email" required maxLength={254} value={email} onChange={e=>setEmail(e.target.value)}/></label>
 <label>Password<input type="password" autoComplete={register?'new-password':'current-password'} required minLength={12} maxLength={256} value={password} onChange={e=>setPassword(e.target.value)}/></label>
 {register&&<p className="fine">Use at least 12 characters.</p>}<ErrorNotice error={error}/><Button size="lg" disabled={busy}>{busy?'Opening…':register?'Create account':'Sign in'}<Icon/></Button>
 </form><Button variant="ghost" disabled={busy} onClick={()=>{setRegister(!register);setError(undefined);setPassword('');}}>{register?'Already have an account? Sign in':'New here? Create an account'}</Button></section></main>;
}
