import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { useApp } from '../store';
import { Badge, Button, ErrorNotice } from './ui';
import type { ReactNode } from 'react';
import { useAuth } from './Accounts';
export function Shell({children,crumb,exit,wide=false}:{children:ReactNode;crumb?:string;exit?:boolean;wide?:boolean}) {
  const health=useQuery({queryKey:['health'],queryFn:api.health,retry:1,staleTime:30000});
  const voice=useApp(s=>s.voice),toggle=useApp(s=>s.toggleVoice);
  const auth=useAuth();
  return <div className={`app-shell ${wide?'wide':''}`}><header className="bar"><Link to="/plan" className="logo"><img src="/prepcrew.svg" width="28" height="28" alt="" aria-hidden="true" style={{display:'block',flexShrink:0}}/>PrepCrew</Link>{crumb&&<span className="crumb">/ {crumb}</span>}<span className="grow"/><Badge tone={health.isError?'warn':''}>{health.isError?'API unavailable':health.data?.demo?'Recorded demo':health.data?'Live session':'Connecting…'}</Badge><Button variant="ghost" size="sm" onClick={toggle}>{voice?'Sound on':'Sound off'}</Button>{auth?.state?.user&&<><Button asChild variant="ghost" size="sm"><Link to="/history">Practice history</Link></Button><Button asChild variant="ghost" size="sm"><Link to="/account">Account</Link></Button><Button variant="ghost" size="sm" onClick={()=>void auth.logout().catch(()=>{})}>Sign out</Button></>}{exit?<Button asChild variant="outline" size="sm"><Link to="/plan">Exit</Link></Button>:<span className="profile-avatar">{auth?.state?.user?.name[0]?.toUpperCase()||'P'}</span>}</header><ErrorNotice error={auth?.error}/>{children}</div>;
}
