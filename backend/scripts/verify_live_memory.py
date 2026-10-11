"""One explicit Backboard CRUD/search/erasure check, using synthetic content only.

--live permits provider usage. Never runs in the automated/paid-free suite.
"""
import argparse
import asyncio
import json
import time
from uuid import uuid4

from app.v2 import memory


async def main():
    aid=mid=None;measurements=[]
    async def call(method,path,**kwargs):
        start=time.perf_counter()
        result=await memory.request(method,path,**kwargs)
        measurements.append({'operation':method+' '+path.split('/')[-1],
            'latency_ms':round((time.perf_counter()-start)*1000)})
        return result
    marker=uuid4().hex
    content='Synthetic PrepCrew acceptance fixture: practice a rate-limiter failure-policy trade-off.'
    try:
        out=await call('POST','assistants',json={'name':'PrepCrew synthetic acceptance '+marker,
            'system_prompt':'Synthetic API acceptance fixture, not a real candidate. Store supplied test content only.'})
        aid=memory.safe_id(out.get('assistant_id'))
        out=await call('POST',f'assistants/{aid}/memories',json={'content':content,
            'metadata':{'prepcrew_memory_id':marker,'synthetic':True}})
        mid=memory.safe_id(out.get('memory_id') or out.get('id'))
        listed=await call('GET',f'assistants/{aid}/memories',params={'page':1,'page_size':10})
        assert any((m.get('metadata') or {}).get('prepcrew_memory_id')==marker for m in listed.get('memories',[])), 'Memory list did not return provenance metadata'
        found=await call('POST',f'assistants/{aid}/memories/search',json={'query':'rate-limiter failure policy','limit':5})
        assert any((m.get('id') or m.get('memory_id'))==mid for m in found.get('memories',[])), 'Synthetic memory was not found by this search; no polling/rerun performed'
        await call('DELETE',f'assistants/{aid}/memories/{mid}')
        remaining=await call('GET',f'assistants/{aid}/memories',params={'page':1,'page_size':10})
        assert not any((m.get('id') or m.get('memory_id'))==mid for m in remaining.get('memories',[]))
        print(json.dumps({'status':'passed','checks':['create','provenance_metadata','semantic_search','delete'],
            'measurements':measurements,'cost_usd':None,'cost_note':'Backboard did not return billed cost in these responses.'},indent=2))
    finally:
        if aid:
            try:await memory.request('DELETE',f'assistants/{aid}')
            except memory.ProviderError as exc:
                if exc.status!=404:raise
        print('Synthetic Backboard assistant removed.' if aid else 'No synthetic Backboard assistant created.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',required=True)
    parser.parse_args()
    asyncio.run(main())
