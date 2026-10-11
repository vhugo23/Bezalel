import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from app.v2 import memory
from app import config


def test_remote_ranking_never_promotes_unknown_memories_or_remote_text():
    rows=[{'id':'local-a','external_id':'remote-a','text':'Verified A'},
          {'id':'local-b','external_id':'remote-b','text':'Verified B'}]
    ranked=memory.ranked_local(rows,['unverified-other-user','remote-b','remote-b'])
    assert [r['id'] for r in ranked] == ['local-b','local-a']
    assert ranked[0]['text'] == 'Verified B'


@pytest.mark.parametrize('score,expected',[(0,1),(49,1),(50,2),(74,2),(75,3),(100,3)])
def test_follow_up_depth_is_bounded_authored_practice_setting(score,expected):
    assert memory.follow_up_depth(score)==expected
    assert 1<=memory.follow_up_depth(score,5)<=5


def test_recall_uses_canonical_local_text_after_backboard_ranking(monkeypatch):
    monkeypatch.setattr(memory,'enabled',lambda:True)
    fetch=AsyncMock(return_value=[{'id':'m','external_id':'external','text':'A locally verified gap.','source_session_id':'s','evidence_seq':[17]}])
    monkeypatch.setattr(memory.db,'fetch',fetch)
    monkeypatch.setattr(memory.db,'one',AsyncMock(return_value={'assistant_id':'assistant'}))
    monkeypatch.setattr(memory,'request',AsyncMock(return_value={'memories':[{'id':'external','content':'Fabricated memory text.'}]}))
    result=asyncio.run(memory.recall('owner',['sw.system_design'],'rate limiter'))
    assert result['text']=='A locally verified gap.' and result['retrieval']=='backboard'
    assert fetch.call_args.args[1:]==('owner',['sw.system_design'])


def test_recall_failure_falls_back_without_breaking_a_session(monkeypatch):
    monkeypatch.setattr(memory,'enabled',lambda:True)
    monkeypatch.setattr(memory.db,'fetch',AsyncMock(return_value=[{'id':'m','text':'Verified local fallback.','external_id':None}]))
    monkeypatch.setattr(memory.db,'one',AsyncMock(return_value={'assistant_id':'assistant'}))
    monkeypatch.setattr(memory,'request',AsyncMock(side_effect=TimeoutError()))
    result=asyncio.run(memory.recall('owner',['sw.system_design'],'rate limiter'))
    assert result['retrieval']=='postgres' and result['text']=='Verified local fallback.'


def test_provider_errors_never_include_response_bodies_or_keys(monkeypatch):
    monkeypatch.setattr(config,'BACKBOARD_API_KEY','synthetic-not-a-real-key')
    monkeypatch.setattr(memory,'_transport',httpx.MockTransport(lambda _:httpx.Response(401,json={'detail':'sensitive provider body'})))
    with pytest.raises(memory.ProviderError) as exc:
        asyncio.run(memory.request('GET','assistants'))
    assert str(exc.value)=='Backboard HTTP 401'


def test_remote_recovery_reads_metadata_from_list_not_search(monkeypatch):
    request=AsyncMock(return_value={'memories':[{'id':'external','metadata':{'prepcrew_memory_id':'local'}}]})
    monkeypatch.setattr(memory,'request',request)
    assert asyncio.run(memory.remote_matches('assistant','local'))==['external']
    assert request.call_args.args==('GET','assistants/assistant/memories')


def test_external_ids_cannot_change_request_paths():
    with pytest.raises(ValueError):memory.safe_id('../another-assistant')


def test_erasure_recovers_duplicates_across_pages(monkeypatch):
    page1=[{'id':'first','metadata':{'prepcrew_memory_id':'local'}}]+[{'id':f'other-{i}'} for i in range(99)]
    request=AsyncMock(side_effect=[{'memories':page1,'total_pages':2},
        {'memories':[{'id':'second','metadata':{'prepcrew_memory_id':'local'}}],'total_pages':2}])
    monkeypatch.setattr(memory,'request',request)
    assert asyncio.run(memory.remote_matches('assistant','local'))==['first','second']
