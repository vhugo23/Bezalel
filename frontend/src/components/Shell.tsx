import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { useApp } from '../store';
import { Badge, Button, Icon } from './ui';
import type { ReactNode } from 'react';
export function Shell({children,crumb,exit,wide=false}:{children:ReactNode;crumb?:string;exit?:boolean;wide?:boolean}) {
  const health=useQuery({queryKey:['health'],queryFn:api.health,retry:1,staleTime:30000});
  const voice=useApp(s=>s.voice),toggle=useApp(s=>s.toggleVoice);
  return <div className={`app-shell ${wide?'wide':''}`}><header className="bar"><Link to="/plan" className="logo"><span className="logo-mark"><Icon name="check"/></span>PrepCrew</Link>{crumb&&<span className="crumb">/ {crumb}</span>}<span className="grow"/><Badge tone={health.isError?'warn':''}>{health.isError?'API unavailable':health.data?.demo?'Recorded demo':health.data?'Live session':'Connecting…'}</Badge><Button variant="ghost" size="sm" onClick={toggle}>{voice?'Sound on':'Sound off'}</Button>{exit?<Button asChild variant="outline" size="sm"><Link to="/plan">Exit</Link></Button>:<span className="profile-avatar">J</span>}</header>{children}</div>;
}
