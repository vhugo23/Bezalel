import math
from .models import Stroke, Mark, ClaimDraft

def geometry(mark: Mark, strokes: list[Stroke]):
    ids = [s.id for s in strokes]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate stroke ids')
    target = next((s for s in strokes if s.id == mark.target), None)
    if target is None:
        raise ValueError('Unknown annotation target')
    xs, ys = [p.x for p in target.points], [p.y for p in target.points]
    if not all(math.isfinite(v) for v in xs + ys):
        raise ValueError('Non-finite geometry')
    x, y = max(0, min(xs)-12), max(0, min(ys)-12)
    right, bottom = min(900, max(xs)+12), min(540, max(ys)+12)
    return {'x': x, 'y': y, 'w': right-x, 'h': bottom-y,
            'cx': (x+right)/2, 'cy': (y+bottom)/2, 'rx': (right-x)/2, 'ry': (bottom-y)/2}

def verify(claim: ClaimDraft, events: list[dict], session_id: str):
    index = {e['seq']: e for e in events if e['session_id'] == session_id}
    if not claim.evidence_seq:
        return 'rejected', 'No event evidence supplied'
    if any(seq not in index for seq in claim.evidence_seq):
        return 'rejected', 'Evidence is missing or belongs to another session'
    cited = [index[seq] for seq in claim.evidence_seq]
    if any(e['actor'] != 'candidate' for e in cited):
        return 'rejected', 'Interviewer annotations cannot be graded as candidate work'
    if claim.rule == 'drawing':
        valid = all(e['kind'] == 'stroke' for e in cited)
    elif claim.rule == 'board_explanation':
        valid = all(e['kind'] == 'turn' and e['payload'].get('board') and not e['payload'].get('q') for e in cited)
    elif claim.rule == 'question':
        valid = all(e['kind'] == 'turn' and e['payload'].get('q') for e in cited)
    elif claim.rule == 'tool_action':
        valid = all(e['kind'] in ('command','edit','part_drop','probe') and
                    e['payload'].get('source') == 'validated_simulator' and
                    isinstance(e['payload'].get('revision'),int) and
                    bool(e['payload'].get('engine_version')) for e in cited)
    else:
        valid = all(e['kind'] == 'turn' for e in cited) and bool(claim.quotes)
    if not valid:
        return 'rejected', 'Cited events do not support the required kind of evidence'
    if claim.rule != 'drawing':
        if len(claim.quotes) != len(cited) or any(not q.strip() or q not in e['payload'].get('text','') for q,e in zip(claim.quotes,cited)):
            return 'rejected', 'An exact evidence quote is missing or does not match'
    return 'verified', 'Event references and exact evidence checked; model interpretation is not a proof'
