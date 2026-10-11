import math
from .models import BoardElement, Stroke, Mark, ClaimDraft

def item_bounds(item: BoardElement | Stroke):
    if isinstance(item, BoardElement):
        return item.bounds()
    xs, ys = [p.x for p in item.points], [p.y for p in item.points]
    return min(xs), min(ys), max(xs), max(ys)

def geometry(mark: Mark, items: list[BoardElement] | list[Stroke]):
    ids = [s.id for s in items]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate board element ids')
    target = next((s for s in items if s.id == mark.target), None)
    if target is None:
        raise ValueError('Unknown annotation target')
    left, top, right, bottom = item_bounds(target)
    if not all(math.isfinite(v) for v in (left, top, right, bottom)):
        raise ValueError('Non-finite geometry')
    x, y, right, bottom = left-12, top-12, right+12, bottom+12
    # Legacy strokes lived on a fixed 900 x 540 board; Excalidraw boards are unbounded.
    if isinstance(target, Stroke):
        x, y, right, bottom = max(0, x), max(0, y), min(900, right), min(540, bottom)
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
