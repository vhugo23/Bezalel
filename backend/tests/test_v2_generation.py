import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from google import genai
from app.v2 import generation
from app.v2.models import Critique

def test_rubric_wire_relaxes_complexity_but_local_bounds_stay_enforced():
    from app.v2.models import RubricEvaluation
    original=RubricEvaluation.model_json_schema()
    wire=generation.provider_schema(RubricEvaluation)
    assert 'maxItems' not in wire['properties']['criteria']
    assert original['properties']['criteria']['maxItems']==8
    with pytest.raises(ValueError):RubricEvaluation(criteria=[{'id':'scope'}]*9)


def test_strict_schema_uses_json_schema_wire_field(monkeypatch):
    monkeypatch.setattr(generation,'DEMO',False)
    monkeypatch.setattr(generation.db,'execute',AsyncMock())
    captured=[]
    async def generate_content(**kwargs):
        captured.append(kwargs['config'])
        return SimpleNamespace(text='{"marks": []}',usage_metadata=SimpleNamespace(prompt_token_count=101,candidates_token_count=19,thoughts_token_count=3))
    class AsyncClient:
        models=SimpleNamespace(generate_content=generate_content)
        async def __aenter__(self):return self
        async def __aexit__(self,*_):pass
    monkeypatch.setattr(genai,'Client',lambda **_:SimpleNamespace(aio=AsyncClient()))
    output,_,_=asyncio.run(generation.generate('whiteboard_critique','s','test',Critique,image=b'png'))
    assert output.marks==[]
    config=captured[0]
    assert config.response_schema is None
    assert config.response_json_schema['$defs']['Mark']['additionalProperties'] is False
    assert config.response_json_schema['properties']['marks']['maxItems']==4
    success=next(c for c in generation.db.execute.call_args_list if 'schema_ok=true' in c.args[0])
    assert success.args[-2:]==(101,22)


def test_provider_error_audits_status_without_leaking_body(monkeypatch):
    monkeypatch.setattr(generation,'DEMO',False)
    audit=AsyncMock()
    monkeypatch.setattr(generation.db,'execute',audit)
    class ProviderError(Exception):code=400
    async def generate_content(**_):raise ProviderError('sensitive provider body')
    class AsyncClient:
        models=SimpleNamespace(generate_content=generate_content)
        async def __aenter__(self):return self
        async def __aexit__(self,*_):pass
    monkeypatch.setattr(genai,'Client',lambda **_:SimpleNamespace(aio=AsyncClient()))
    with pytest.raises(ValueError,match='Model unavailable'):
        asyncio.run(generation.generate('whiteboard_critique','s','test',Critique))
    error=audit.call_args.args[2]
    assert error=='ProviderError (HTTP 400)'
    assert 'sensitive' not in error


def test_validation_retry_supplies_safe_correction_and_keeps_array_limits(monkeypatch):
    import json
    monkeypatch.setattr(generation,'DEMO',False)
    audit=AsyncMock();monkeypatch.setattr(generation.db,'execute',audit)
    captured=[]
    mark={'kind':'circle','severity':'info','speech':'private candidate content','target':'shape'}
    async def generate_content(**kwargs):
        captured.append(kwargs['contents'][0])
        return SimpleNamespace(text=json.dumps({'marks':[mark]*5 if len(captured)==1 else []}))
    class AsyncClient:
        models=SimpleNamespace(generate_content=generate_content)
        async def __aenter__(self):return self
        async def __aexit__(self,*_):pass
    monkeypatch.setattr(genai,'Client',lambda **_:SimpleNamespace(aio=AsyncClient()))
    output,_,_=asyncio.run(generation.generate('whiteboard_critique','s','Review the board.',Critique))
    assert output.marks==[] and len(captured)==2
    assert 'marks: too_long' in captured[1]
    assert 'private candidate content' not in captured[1]
    attempts=[c for c in audit.call_args_list if 'INSERT INTO generation_jobs' in c.args[0]]
    assert len(attempts)==2 and attempts[1].args[7]==2


def test_failed_vision_preserves_png_and_candidate_artifact(monkeypatch,tmp_path):
    import base64
    from datetime import datetime,timezone
    from app.v2 import service
    from app.v2.models import BoardInput,BoardElement,Event
    from tests.board_fixtures import element
    stroke=BoardElement(**element('shape'))
    png=b'\x89PNG\r\n\x1a\nfixture'
    monkeypatch.setattr(service,'ROOT',tmp_path)
    monkeypatch.setattr(service,'DEMO',False)
    monkeypatch.setattr(service,'require_session',AsyncMock(return_value={'status':'live'}))
    monkeypatch.setattr(service,'events',AsyncMock(return_value=[Event(session_id='s',seq=1,kind='stroke',actor='candidate',step=1,payload=stroke.model_dump(),ts=datetime.now(timezone.utc))]))
    monkeypatch.setattr(service,'generate',AsyncMock(side_effect=ValueError('provider unavailable')))
    logged=AsyncMock();monkeypatch.setattr(service,'log',logged)
    class Context:
        def __init__(self,value):self.value=value
        async def __aenter__(self):return self.value
        async def __aexit__(self,*_):pass
    event=Event(session_id='s',seq=1,kind='stroke',actor='candidate',step=1,payload=stroke.model_dump(),ts=datetime.now(timezone.utc))
    conn=SimpleNamespace(execute=AsyncMock(),fetchval=AsyncMock(return_value=1),
        fetchrow=AsyncMock(return_value={'status':'live','step':1,'engine_state':{}}),
        fetch=AsyncMock(return_value=[event.model_dump()]),transaction=lambda:Context(None))
    monkeypatch.setattr(service.db,'pool',AsyncMock(return_value=SimpleNamespace(acquire=lambda:Context(conn))))
    with pytest.raises(ValueError,match='provider unavailable'):
        asyncio.run(service.board('s',BoardInput(elements=[stroke],png=base64.b64encode(png).decode())))
    files=list((tmp_path/'.artifacts').glob('*.png'))
    assert len(files)==1 and files[0].read_bytes()==png
    assert any('INSERT INTO artifacts' in c.args[0] for c in conn.execute.call_args_list)
    assert not any('UPDATE artifacts' in c.args[0] for c in conn.execute.call_args_list)
    assert logged.call_args.args[4]['artifact_id']==files[0].stem
