// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest';
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();vi.resetModules();});

test('split-host socket uses an authenticated POST then sends only a scoped ticket in the protocol',async()=>{
 vi.stubEnv('VITE_WS_URL','https://prepcrew-test.onrender.com');vi.stubEnv('VITE_API_URL','');vi.resetModules();
 const token='a'.repeat(43);const fetch=vi.fn(async(_url:RequestInfo|URL,_options?:RequestInit)=>new Response(JSON.stringify({token,expires_in_seconds:45}),{status:200}));
 const socket=vi.fn(function(this:unknown,url:string,protocols?:string[]){return {url,protocols};});
 vi.stubGlobal('fetch',fetch);vi.stubGlobal('WebSocket',socket);
 const {openSessionSocket}=await import('./client');await openSessionSocket('/ws/v2/voice/session-a','session-a','voice');
 expect(fetch.mock.calls[0][0]).toBe('/api/v2/sessions/session-a/socket-ticket');
 const options=fetch.mock.calls[0][1] as RequestInit;
 expect(options.credentials).toBe('include');expect(options.method).toBe('POST');expect(new Headers(options.headers).get('X-PrepCrew-Request')).toBe('1');
 expect(options.body).toBe(JSON.stringify({channel:'voice'}));
 expect(socket).toHaveBeenCalledWith('wss://prepcrew-test.onrender.com/ws/v2/voice/session-a',['prepcrew',`prepcrew-ticket.${token}`]);
});

test('failed ticket issuance never opens an unauthenticated socket',async()=>{
 vi.stubEnv('VITE_WS_URL','https://prepcrew-test.onrender.com');vi.resetModules();
 vi.stubGlobal('fetch',vi.fn(async()=>new Response('{}',{status:401})));const socket=vi.fn();vi.stubGlobal('WebSocket',socket);
 const {openSessionSocket}=await import('./client');await expect(openSessionSocket('/ws/v2/sessions/session-a','session-a','events')).rejects.toThrow('Could not authorize');
 expect(socket).not.toHaveBeenCalled();
});
