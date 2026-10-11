import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.v2.integrity import geometry
from app.v2.models import BoardElement, BoardElementsInput, Critique, Event, Mark
from app.v2.service import active_strokes, demo_matches, vision_element_log
from app.v2.assessment import compact, recorded_evaluation
from tests.board_fixtures import element

ROOT = Path(__file__).resolve().parents[2]


def test_elements_must_be_drawable_bounded_and_self_consistent():
    BoardElement(**element('box'))
    BoardElement(**element('arrow', 'arrow'))
    BoardElement(**element('note', 'text', link='https://example.com/design'))
    bad = [
        element('img', 'image'), element('embed', 'embeddable'),
        {**element('box'), 'version': 2},
        {**element('box'), 'id': 'other'},
        element('box', x=float('nan')), element('box', width=-1), element('box', y=1e9),
        element('box', isDeleted=None), element('box', customData={'dana': True}),
        element('box', link='javascript:alert(1)'),
        element('line', 'line', points=[[0, 0], [1]]), element('line', 'line', points=[]),
        element('text', 'text', text='x' * 2001),
        element('../bad'),
        element('box', note='x' * 300_001),
    ]
    for raw in bad:
        with pytest.raises(ValidationError):
            BoardElement(**raw)
    with pytest.raises(ValidationError):
        BoardElementsInput(step=0, elements=[])
    with pytest.raises(ValidationError):
        BoardElementsInput(step=0, elements=[element(f'e{i}') for i in range(201)])


def test_bounds_cover_rotation_and_linear_points_without_clamping_to_a_fixed_board():
    assert BoardElement(**element('box', x=-500, y=2000)).bounds() == (-500, 2000, -400, 2050)
    turned = BoardElement(**element('box', x=0, y=0, width=100, height=50, angle=3.141592653589793 / 2)).bounds()
    assert [round(v) for v in turned] == [25, -25, 75, 75]
    assert BoardElement(**element('a', 'arrow', x=10, y=10, points=[[0, 0], [-20, 30], [40, 5]])).bounds() == (-10, 10, 50, 40)
    mark = Mark(kind='circle', severity='good', speech='Clear.', target='box')
    assert geometry(mark, [BoardElement(**element('box', x=-500, y=2000))])['x'] == -512
    with pytest.raises(ValueError):
        geometry(mark, [BoardElement(**element('other'))])


def _event(seq, payload, step=0, kind='stroke'):
    return Event(session_id='s', seq=seq, kind=kind, actor='candidate', step=step, payload=payload, ts=datetime.now(timezone.utc))


def test_active_board_uses_newest_version_and_drops_deleted_elements():
    log = [_event(1, element('box')), _event(2, element('box', version=3, x=99)), _event(3, element('gone')),
           _event(4, element('gone', version=2, isDeleted=True)), _event(5, element('other'), step=1)]
    active = active_strokes(log, 0)
    assert list(active) == ['box'] and active['box']['element']['x'] == 99


def test_vision_log_folds_box_labels_and_keeps_arrow_connections():
    box = BoardElement(**element('limiter', boundElements=[{'id': 'limiter-label', 'type': 'text'}]))
    label = BoardElement(**element('limiter-label', 'text', text='Rate limiter', containerId='limiter'))
    arrow = BoardElement(**element('flow', 'arrow', startBinding={'elementId': 'gateway'}, endBinding={'elementId': 'limiter'},
                                   points=[[i, i % 7] for i in range(200)]))
    loose = BoardElement(**element('note', 'text', text='token bucket'))
    log = vision_element_log([box, label, arrow, loose])
    assert [item['id'] for item in log] == ['limiter', 'flow', 'note']
    assert log[0]['label'] == 'Rate limiter' and log[2]['label'] == 'token bucket'
    assert log[1]['connects'] == ['gateway', 'limiter'] and len(log[1]['sampled_points']) == 16


def _demo_elements(nudge=0):
    elements = []
    for stroke in json.loads((ROOT / 'contracts/demo-board.json').read_text()):
        xs, ys = [p['x'] for p in stroke['points']], [p['y'] for p in stroke['points']]
        kind = {'rect': 'rectangle', 'arrow': 'arrow', 'path': 'line', 'text': 'text'}[stroke['kind']]
        extra = {'text': stroke['label'], 'originalText': stroke['label']} if kind == 'text' else {}
        elements.append(BoardElement(**element(stroke['id'], kind, x=min(xs) + nudge, y=min(ys), **extra)))
        if kind == 'rectangle' and stroke['label']:
            elements.append(BoardElement(**element(stroke['id'] + '-label', 'text', text=stroke['label'], containerId=stroke['id'])))
    return elements


def test_recorded_demo_critique_matches_only_the_unchanged_demo_board():
    demo = _demo_elements()
    assert demo_matches(demo)
    assert demo_matches(_demo_elements(nudge=3))
    assert not demo_matches(_demo_elements(nudge=20))
    assert not demo_matches(demo[:-1])
    relabelled = [BoardElement(**element(e.id, 'text', text='Cache', containerId=e.element['containerId'])) if e.id == 'limiter-label' else e for e in demo]
    assert not demo_matches(relabelled)
    critique = Critique.model_validate_json((ROOT / 'contracts/demo-critique.json').read_text())
    shown = [e for e in demo if not e.element.get('containerId')]
    for mark in critique.marks:
        assert geometry(mark, shown)['w'] > 0


def test_evaluator_prompts_see_drawing_facts_not_raw_geometry_and_skip_deletions():
    drawn = {'session_id': 's', 'seq': 1, 'kind': 'stroke', 'actor': 'candidate', 'step': 1, 'payload': element('box', 'text', text='Redis')}
    small = compact(drawn)
    assert small['payload'] == {'id': 'box', 'kind': 'text', 'label': 'Redis', 'deleted': False}
    assert compact({'kind': 'turn', 'payload': {'text': 'hi'}}) == {'kind': 'turn', 'payload': {'text': 'hi'}}
    deleted = {**drawn, 'seq': 2, 'payload': element('box', version=2, isDeleted=True)}
    drawing = lambda events: next(c for c in recorded_evaluation('Whiteboard', events)['criteria'] if c['id'] == 'drawing')['claims']
    assert drawing([deleted]) == []
    assert drawing([drawn, deleted])[0]['evidence_seq'] == [1]
