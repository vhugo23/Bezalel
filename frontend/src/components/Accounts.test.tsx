// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { AccountProvider, AccountWorkspace } from './Accounts';
import { api, type Model } from '../api/client';
import { useApp } from '../store';

afterEach(()=>{cleanup();vi.restoreAllMocks();useApp.getState().bindAccount(null);});

test('a concurrent same-account refresh waits for server plan restoration',async()=>{
 const account={id:'synthetic-account',name:'Synthetic candidate',email:'candidate@example.test'};
 useApp.getState().bindAccount(null);
 vi.spyOn(api,'auth').mockResolvedValue({enabled:true,user:account});
 let restore!:(history:Model<'History'>)=>void;
 vi.spyOn(api,'history').mockImplementation(()=>new Promise(resolve=>{restore=resolve;}));
 vi.spyOn(api,'plan').mockResolvedValue({id:'restored-plan',intake:{user_id:account.id,name:account.name,role:'Engineer',companies:[],struggles:[],question:'',link:''},primary_domain:'sw',skills:[],tracks:[],source:'Synthetic fixture'});
 function Workspace(){const plan=useApp(s=>s.planId);return <p>Restored: {plan||'missing'}</p>;}
 render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AccountProvider><Routes><Route element={<AccountWorkspace/>}><Route path="/" element={<Workspace/>}/></Route></Routes></AccountProvider></MemoryRouter></QueryClientProvider>);
 await waitFor(()=>expect(api.history).toHaveBeenCalledTimes(1));
 await act(async()=>{window.dispatchEvent(new Event('focus'));});
 expect(screen.queryByText('Restored: missing')).toBeNull();
 await act(async()=>{restore({latest_plan_id:'restored-plan',sessions:[],next_cursor:null});});
 expect(await screen.findByText('Restored: restored-plan')).toBeTruthy();
 expect(api.history).toHaveBeenCalledTimes(1);
});

test('pre-account migration retains only an operator locator and clears the old draft',async()=>{
 useApp.setState({accountId:null,planId:'old-plan',planJobId:null,intake:{user_id:'old-workspace',name:'Synthetic old account',role:'Engineer',companies:[],struggles:[],question:'PRIVATE_DRAFT_CANARY',link:''}});
 localStorage.removeItem('prepcrew-legacy-workspace-id');
 vi.spyOn(api,'auth').mockResolvedValue({enabled:true,user:null});
 render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AccountProvider><Routes><Route element={<AccountWorkspace/>}><Route path="/" element={<p>Workspace</p>}/></Route></Routes></AccountProvider></MemoryRouter></QueryClientProvider>);
 await screen.findByRole('heading',{name:'Welcome back.'});
 expect(localStorage.getItem('prepcrew-legacy-workspace-id')).toBe('old-workspace');
 expect(useApp.getState().planId).toBeNull();
 expect(localStorage.getItem('prepcrew-profile-v2')).not.toContain('PRIVATE_DRAFT_CANARY');
});
