// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest';
import { api, apiFetch, apiJson, invalidateAccountRequests } from './client';

afterEach(()=>{vi.unstubAllGlobals();invalidateAccountRequests();});

test('late private response from an old account cannot populate a new account cache',async()=>{
 let deliver!:(response:Response)=>void;
 vi.stubGlobal('fetch',vi.fn(()=>new Promise<Response>(resolve=>{deliver=resolve;})));
 const pending=api.history();
 invalidateAccountRequests();
 deliver(new Response(JSON.stringify({sessions:[{id:'private-old-session'}]}),{status:200}));
 await expect(pending).rejects.toThrow('account changed');
});

test('account switch while a response body is arriving also rejects old private data',async()=>{
 let body!:(value:unknown)=>void;
 const response={ok:true,status:200,json:()=>new Promise(resolve=>{body=resolve;})} as Response;
 vi.stubGlobal('fetch',vi.fn(async()=>response));
 const received=await apiFetch('/history');
 const parsing=apiJson(received);invalidateAccountRequests();body({private:'old account'});
 await expect(parsing).rejects.toThrow('account changed');
});

test('typed client includes cookies and the protection header for binary and JSON writes',async()=>{
 const fetch=vi.fn(async(_input:RequestInfo|URL,_init?:RequestInit)=>new Response('{}'));vi.stubGlobal('fetch',fetch);
 await apiFetch('/sources/upload',{method:'POST',headers:{'Content-Type':'text/plain'},body:'synthetic'});
 const init=fetch.mock.calls[0][1]!;
 expect(init.credentials).toBe('include');
 expect((init.headers as Headers).get('X-PrepCrew-Request')).toBe('1');
 expect((init.headers as Headers).get('Content-Type')).toBe('text/plain');
});
