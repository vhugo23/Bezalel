// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router';
import { FleetPage, LessonPage } from './Fleet';
import { api, type Model } from '../api/client';

vi.mock('../components/Shell',()=>({Shell:({children}:{children:React.ReactNode})=><>{children}</>}));
const report:Model<'Report'>={session_id:'s',status:'graded',claims:[],evaluators:[],demo:false,partial:false,scores:[]};
function mount(lesson=false,entry?:string){
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
 render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[entry||(lesson?'/lesson/s':'/fleet/s')]}><Routes><Route path="/fleet/:id" element={<FleetPage/>}/><Route path="/lesson/:id" element={<LessonPage/>}/><Route path="/session/:id" element={<p>Retest opened</p>}/></Routes></MemoryRouter></QueryClientProvider>);
}
beforeEach(()=>{
 vi.spyOn(api,'report').mockResolvedValue(report);
 vi.spyOn(api,'session').mockResolvedValue({id:'s',track_id:'t',title:'Practice',domain:'sw',engine_id:'conceptual',paused:false,step:3,status:'graded',opening:'Design an API',demo:false,events:[]});
 vi.spyOn(api,'metrics').mockResolvedValue({rows:[],hypertables:[],aggregates:[]});
});
afterEach(()=>{cleanup();vi.restoreAllMocks();});

test('a review without a verified gap offers no invented lesson',async()=>{
 mount();await screen.findByText('No verified gap to turn into a lesson in this review. Your evidence is available above.');
 expect(screen.queryByRole('link',{name:'Open the lesson'})).toBeNull();
});

test('partial review can resume and does not display an invented zero',async()=>{
 vi.mocked(api.report).mockResolvedValue({...report,partial:true});
 const end=vi.spyOn(api,'end').mockResolvedValue(report);
 mount();fireEvent.click(await screen.findByRole('button',{name:'Retry review'}));
 await waitFor(()=>expect(end).toHaveBeenCalledWith('s'));
 await waitFor(()=>expect(screen.queryByRole('button',{name:'Retry review'})).toBeNull());
 expect(screen.queryByText('0 / 100')).toBeNull();
});

test('a lesson citation opens the exact saved source event',async()=>{
 vi.mocked(api.session).mockResolvedValue({id:'s',track_id:'t',title:'Practice',domain:'sw',engine_id:'conceptual',paused:false,step:3,status:'graded',opening:'Design an API',demo:false,events:[{
  session_id:'s',seq:17,actor:'candidate',kind:'turn',step:2,payload:{text:'My specific failure-policy explanation.'},ts:'2026-10-10T18:00:00Z'}]});
 mount(false,'/fleet/s?evidence=17');
 const dialog=await screen.findByRole('dialog');
 expect(dialog.textContent).toContain('My specific failure-policy explanation.');
 expect(dialog.textContent).toContain('Event #17');
});

test('lesson generation replaces the preview with saved teaching and a runnable retest',async()=>{
 const preview:Model<'Lesson'>={body:'',title:'Your next practice',reason:'An evidenced gap',evidence_seq:[17],claim_id:'c',skill_id:'sw.system_design',ai_generated:false,practice:'',retest_ready:false};
 vi.spyOn(api,'lesson').mockResolvedValue(preview);
 const generate=vi.spyOn(api,'generateLesson').mockResolvedValue({...preview,id:'l',title:'Choosing a failure policy',body:'A saved lesson about the availability trade-off.',practice:'Explain a changed constraint.',ai_generated:true,retest_ready:true});
 mount(true);fireEvent.click(await screen.findByRole('button',{name:'Generate my lesson'}));
 await screen.findByRole('heading',{name:'Choosing a failure policy'});
 expect(generate).toHaveBeenCalledTimes(1);
 expect(screen.getByRole('button',{name:'Start retest'})).toBeDefined();
 expect(screen.getByRole('link',{name:'Event #17'})).toBeDefined();
 expect(screen.queryByRole('button',{name:'Generate my lesson'})).toBeNull();
});
