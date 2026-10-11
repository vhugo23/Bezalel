import { Link, NavLink } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { Button, ErrorNotice } from './ui';
import { useEffect, useRef, type ReactNode } from 'react';
import { useAuth } from './Accounts';
export function Shell({children,crumb,exit,wide=false}:{children:ReactNode;crumb?:string;exit?:boolean;wide?:boolean}) {
  const health=useQuery({queryKey:['health'],queryFn:api.health,retry:1,staleTime:30000});
  const auth=useAuth();
  const menu=useRef<HTMLDetailsElement>(null);
  useEffect(()=>{
    const dismiss=(event:PointerEvent)=>{if(event.target instanceof Node&&!menu.current?.contains(event.target)&&menu.current)menu.current.open=false;};
    document.addEventListener('pointerdown',dismiss);
    return ()=>document.removeEventListener('pointerdown',dismiss);
  },[]);
  const user=auth?.state?.user;
  const status=health.isError?'Connection unavailable':health.data?.demo?'Recorded demo':health.data?'Connected':'Connecting…';
  return <div className={`app-shell ${wide?'wide':''}`}>
    <header className="bar workspace-bar">
      <div className="header-brand"><Link to="/plan" className="logo"><img src="/prepcrew.svg" width="27" height="27" alt="" aria-hidden="true"/>PrepCrew</Link>{crumb&&<span className="crumb">{crumb}</span>}</div>
      {user&&<nav className="header-nav" aria-label="Main navigation"><NavLink to="/plan">Workspace</NavLink><NavLink to="/resume">Resume</NavLink><NavLink to="/history">History</NavLink></nav>}
      <div className="header-actions">
        <span className={`connection-status ${health.isError?'unavailable':health.data?'connected':''}`} role="status" title={status}><i aria-hidden="true"/><span>{status}</span></span>
        {exit&&<Button asChild variant="outline" size="sm"><Link to="/plan">Exit session</Link></Button>}
        {user&&<details ref={menu} className="account-menu" onKeyDown={event=>{if(event.key==='Escape'){event.currentTarget.open=false;event.currentTarget.querySelector('summary')?.focus();}}}>
          <summary aria-label="Account menu"><span className="profile-avatar">{user.name[0]?.toUpperCase()||'P'}</span><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m5 6 3 3 3-3"/></svg></summary>
          <div className="account-popover" onClick={event=>{if(event.target instanceof Element&&event.target.closest('a,button')&&menu.current)menu.current.open=false;}}><div className="account-menu-name">{user.name}</div><Link to="/plan">Workspace</Link><Link to="/resume">Resume check</Link><Link to="/history">Practice history</Link><Link to="/account">Account &amp; data</Link><button type="button" onClick={()=>void auth?.logout().catch(()=>{})}>Sign out</button></div>
        </details>}
      </div>
    </header>
    <ErrorNotice error={auth?.error}/>{children}
  </div>;
}
