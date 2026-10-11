import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.v2.models import Stroke, Mark, ClaimDraft, Critique
from app.v2.integrity import geometry, verify

def event(seq=7, actor='candidate', board=True, session='s'):
    return {'session_id':session,'seq':seq,'kind':'turn','actor':actor,'payload':{'text':'Counters live in Redis.','board':board,'q':False}}

def claim(**values):
    return ClaimDraft(text='Explained while drawing',polarity='strength',evidence_seq=values.get('evidence_seq',[7]),quotes=values.get('quotes',['Counters live in Redis.']),rule='board_explanation')

def test_board_explanation_requires_board_turn_and_exact_quote():
    assert verify(claim(),[event()],'s')[0]=='verified'
    assert verify(claim(),[event(board=False)],'s')[0]=='rejected'
    assert verify(claim(quotes=['Invented quote']),[event()],'s')[0]=='rejected'

@pytest.mark.parametrize('events', [[event(actor='interviewer')],[event(session='other')],[]])
def test_interviewer_missing_and_cross_session_evidence_rejected(events):
    assert verify(claim(),events,'s')[0]=='rejected'

def test_empty_evidence_rejected():
    assert verify(claim(evidence_seq=[]),[event()],'s')[0]=='rejected'

def test_coordinates_come_from_bounds_and_stay_in_canvas():
    stroke=Stroke(id='a',kind='path',points=[{'x':0,'y':0},{'x':900,'y':540}])
    mark=Mark(kind='circle',severity='probe',speech='Why?',target='a')
    box=geometry(mark,[stroke])
    assert box=={'x':0,'y':0,'w':900,'h':540,'cx':450,'cy':270,'rx':450,'ry':270}
    with pytest.raises(ValueError): geometry(mark,[])
    with pytest.raises(ValueError): geometry(mark,[stroke,stroke])
    with pytest.raises(ValidationError): Mark(**mark.model_dump(),x=500)
    with pytest.raises(ValidationError): Stroke(id='a',kind='path',points=[{'x':float('nan'),'y':0}])

def test_recorded_critique_obeys_live_schema():
    root=Path(__file__).resolve().parents[2]
    strokes=[Stroke(**x) for x in json.loads((root/'contracts/demo-board.json').read_text())]
    critique=Critique.model_validate_json((root/'contracts/demo-critique.json').read_text())
    for mark in critique.marks: assert geometry(mark,strokes)['w']>0


def test_compact_vision_log_keeps_ids_endpoints_and_exact_bounds():
    from app.v2.service import vision_stroke_log
    strokes=[Stroke(id='path',kind='path',points=[{'x':i,'y':i%31} for i in range(300)]),Stroke(id='dot',kind='path',points=[{'x':2,'y':3}])]
    compact=vision_stroke_log(strokes)
    assert [s['id'] for s in compact]==['path','dot']
    assert compact[0]['bounds']=={'left':0,'top':0,'right':299,'bottom':30}
    assert len(compact[0]['sampled_points'])==16
    assert compact[0]['sampled_points'][0]==[0,0]
    assert compact[0]['sampled_points'][-1]==[299,20]
    assert compact[1]['sampled_points']==[[2,3]]
