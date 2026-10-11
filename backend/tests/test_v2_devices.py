from datetime import datetime,timezone
import pytest
from fastapi import HTTPException
from app.v2.devices import token_hash
from app.v2.service import validate_snapshot
from app.v2.models import Event,Stroke


def test_private_device_capability_has_fixed_entropy_and_is_not_stored_raw():
    token='ab'*32
    assert len(token_hash(token))==64 and token_hash(token)!=token
    for invalid in ('short','../path',None,'g'*64):
        with pytest.raises(ValueError):token_hash(invalid)


def test_snapshot_must_match_current_step_complete_active_stroke_log():
    stroke=Stroke(id='shape',kind='path',points=[{'x':10,'y':20}])
    event=Event(session_id='s',seq=1,kind='stroke',actor='candidate',step=0,payload=stroke.model_dump(),ts=datetime.now(timezone.utc))
    validate_snapshot([event],0,[stroke])
    removed=event.model_copy(update={'seq':2,'kind':'note','actor':'system','payload':{'remove_strokes':['shape']}})
    for log,step,submitted in (([event,removed],0,[stroke]),([event],1,[stroke]),([event],0,[])):
        with pytest.raises(HTTPException) as error:validate_snapshot(log,step,submitted)
        assert error.value.status_code==409
