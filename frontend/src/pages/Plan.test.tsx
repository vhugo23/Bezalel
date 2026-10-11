// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router';
import { PlanPage } from './Plan';
import { api, type Plan, type Model } from '../api/client';
import { useApp } from '../store';
vi.mock('../components/Shell',()=>({Shell:({children}:{children:React.ReactNode})=><>{children}</>}));
const track=(id:string,domain:string,ready:boolean):Model<'Track'>=>({id,domain,ready,title:id,summary:'Practice this skill',layer:1,recommended:false});
function mount(tracks:Plan['tracks']){
 useApp.setState({planId:'plan'});
 vi.spyOn(api,'plan').mockResolvedValue({id:'plan',intake:useApp.getState().intake,primary_domain:'infra',skills:[],tracks,source:'Authored'});
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
 render(<QueryClientProvider client={client}><MemoryRouter><PlanPage/></MemoryRouter></QueryClientProvider>);
}
afterEach(()=>{cleanup();vi.restoreAllMocks();});
test('only runnable tracks and domains appear, with no custom preview',async()=>{
 const start=vi.spyOn(api,'start').mockRejectedValue(new Error('Test start failure'));
 mount([track('Unavailable infrastructure','infra',false),track('System design','sw',true)]);
 await screen.findByRole('button',{name:'Start session'});
 expect(screen.getAllByRole('tab')).toHaveLength(1);
 expect(screen.queryByText('Unavailable infrastructure')).toBeNull();
 expect(screen.queryByRole('textbox',{name:'Custom topic'})).toBeNull();
 expect(screen.queryByRole('button',{name:/Preview/})).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Start session'}));
 await waitFor(()=>expect(start).toHaveBeenCalledWith('System design',expect.anything()));
});
test('an entirely unavailable plan offers recovery instead of disabled starts',async()=>{
 mount([track('Unavailable infrastructure','infra',false)]);
 await screen.findByRole('heading',{name:'No practice sessions are available yet'});
 expect(screen.getByRole('link',{name:'Update answers'}).getAttribute('href')).toBe('/intake');
 expect(screen.getByRole('button',{name:'Retry'})).toBeDefined();
 expect(screen.queryByRole('button',{name:'Start session'})).toBeNull();
 expect(screen.queryByRole('tab')).toBeNull();
});
test('switching domains starts a track from the selected domain',async()=>{
 const start=vi.spyOn(api,'start').mockRejectedValue(new Error('Test start failure'));
 mount([track('Pi troubleshooting','infra',true),track('System design','sw',true)]);
 await screen.findByRole('button',{name:'Start session'});
 fireEvent.click(screen.getAllByRole('tab')[1]);
 fireEvent.click(screen.getByRole('button',{name:'Start session'}));
 await waitFor(()=>expect(start).toHaveBeenCalledWith('System design',expect.anything()));
});
