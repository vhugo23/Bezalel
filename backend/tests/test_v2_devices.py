from datetime import datetime,timezone
import pytest
from fastapi import HTTPException
from app.v2.devices import token_hash
from app.v2.service import validate_snapshot
from app.v2.models import BoardElement,Event
from tests.board_fixtures import element


def test_private_device_capability_has_fixed_entropy_and_is_not_stored_raw():
    token='ab'*32
    assert len(token_hash(token))==64 and token_hash(token)!=token
    for invalid in ('short','../path',None,'g'*64):
        with pytest.raises(ValueError):token_hash(invalid)


def test_snapshot_must_match_current_step_complete_active_stroke_log():
    shape=BoardElement(**element('shape'))
    event=Event(session_id='s',seq=1,kind='stroke',actor='candidate',step=0,payload=shape.model_dump(),ts=datetime.now(timezone.utc))
    validate_snapshot([event],0,[shape])
    moved=BoardElement(**element('shape',version=2,x=40))
    later=event.model_copy(update={'seq':2,'payload':moved.model_dump()})
    validate_snapshot([event,later],0,[moved])
    deleted=BoardElement(**element('shape',version=3,isDeleted=True))
    gone=event.model_copy(update={'seq':3,'payload':deleted.model_dump()})
    removed=event.model_copy(update={'seq':2,'kind':'note','actor':'system','payload':{'remove_strokes':['shape']}})
    for log,step,submitted in (([event,removed],0,[shape]),([event],1,[shape]),([event],0,[]),([event,later],0,[shape]),
                               ([event,later,gone],0,[moved]),([event,later,gone],0,[deleted])):
        with pytest.raises(HTTPException) as error:validate_snapshot(log,step,submitted)
        assert error.value.status_code==409

