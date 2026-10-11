import { useInfiniteQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { api } from '../api/client';
import { Shell } from '../components/Shell';
import { Badge, Button, ErrorNotice } from '../components/ui';

export function HistoryPage(){
 const history=useInfiniteQuery({queryKey:['history'],initialPageParam:undefined as string|undefined,queryFn:({pageParam})=>api.history(pageParam),getNextPageParam:page=>page.next_cursor||undefined});
 const sessions=history.data?.pages.flatMap(page=>page.sessions||[])||[];
 return <Shell crumb="Your practice"><main className="page"><div className="wrap"><div className="hhead"><div><h1>Pick up where you left off.</h1><p className="sub">Your saved interviews, on any device.</p></div><Button asChild><Link to="/plan">Open your plan</Link></Button></div><ErrorNotice error={history.error}/><section className="card history-list">{history.isPending?<p className="empty-state">Opening your history…</p>:sessions.length?sessions.map(s=><article key={s.id} className="history-entry"><div><h3>{s.title}</h3><p className="fine">{new Date(s.created_at).toLocaleString()}</p></div><Badge>{s.status==='live'?`Step ${s.step+1}`:s.status==='graded'?'Reviewed':s.status==='grading'?'Review in progress':s.status}</Badge><Button variant="outline" size="sm" asChild><Link to={['graded','grading','ended'].includes(s.status)?`/fleet/${s.id}`:`/session/${s.id}`}>{s.status==='live'?'Resume interview':'Open interview'}</Link></Button></article>):<div className="empty-state"><h2>Your first practice starts here.</h2><p>Build a plan and try a track. Your interviews will appear here.</p><Button asChild><Link to="/intake">Build a plan</Link></Button></div>}</section>{history.hasNextPage&&<Button className="top-gap" variant="outline" disabled={history.isFetchingNextPage} onClick={()=>void history.fetchNextPage()}>Load earlier practice</Button>}</div></main></Shell>;
}
