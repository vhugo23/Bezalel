"""Authored practice rubrics; human calibration is still pending.

The event/quote checks adapt the upstream evaluator's assemble-then-validate
contract to v2 sequence references. A score is inseparable from its criterion.
"""
from dataclasses import dataclass, asdict
import hashlib
import json
from .models import RubricEvaluation

VERSION = 'system-design-practice-v2'


@dataclass(frozen=True)
class Criterion:
    id: str
    skill_id: str
    description: str
    rules: tuple[str, ...]
    scored: bool = True
    steps: tuple[int, ...] = (0,1,2)


RUBRICS = {
    'Requirements': [Criterion('scope', 'sw.system_design', 'Clarifies workload, client limits and availability before choosing a design.', ('question','quoted_turn'),steps=(0,))],
    'Whiteboard': [
        Criterion('drawing', 'sw.system_design', 'Records candidate drawing activity; this does not establish architectural quality.', ('drawing',), False, (1,)),
        Criterion('design_reasoning', 'sw.system_design', 'Explains the responsibilities and state consistency of the proposed rate-limiter design during drawing.', ('board_explanation',),steps=(1,)),
    ],
    'Trade-offs': [Criterion('failure_policy', 'sw.system_design', 'Explains an availability/correctness trade-off and its consequences under failure.', ('quoted_turn','board_explanation'),steps=(1,2))],
    'Communication': [
        Criterion('narration', 'sw.system_design', 'Explains while drawing, evidenced by candidate board speech.', ('board_explanation',), False,(1,)),
        Criterion('followup', 'comm.followups', 'Answers an actual interviewer follow-up directly with a concrete explanation. Assess responsiveness and clarity, not technical correctness. No follow-up means unassessed.', ('quoted_turn',)),
    ],
}

ANCHORS = {
    0: 'An explicit attempted answer demonstrates a misconception or inability on this criterion.',
    1: 'Identifies part of the issue but explicitly needs substantial help.',
    2: 'Partially explains the issue; an evidenced limitation remains.',
    3: 'Gives a coherent explanation meeting this criterion.',
    4: 'Gives a precise explanation including consequences or boundary cases.',
}

@dataclass(frozen=True)
class Policy:
    version: str
    evaluators: dict[str, list[Criterion]]


DEFAULT = Policy(VERSION,RUBRICS)


def load(payload, engine_id='conceptual'):
    if not isinstance(payload,dict) or not payload.get('evaluators'):
        if engine_id!='conceptual':raise ValueError('This engine has no reviewed rubric')
        return DEFAULT
    evaluators={}
    raw=payload['evaluators']
    if not isinstance(raw,dict) or not 1<=len(raw)<=6:raise ValueError('Invalid evaluator selection')
    for name,criteria in raw.items():
        if not isinstance(name,str) or not name.strip() or len(name)>80 or not isinstance(criteria,list) or not 1<=len(criteria)<=8:
            raise ValueError('Invalid rubric criteria')
        definitions=[]
        for item in criteria:
            c=Criterion(**item)
            if not c.id or not c.skill_id or not c.description or not c.steps or any(not isinstance(i,int) or not 0<=i<=9 for i in c.steps):
                raise ValueError('Invalid criterion definition')
            if not c.rules or any(rule not in ('question','quoted_turn','board_explanation','drawing') for rule in c.rules):
                raise ValueError('Invalid evidence rule')
            definitions.append(c)
        if len({c.id for c in definitions})!=len(definitions):raise ValueError('Duplicate criterion id')
        evaluators[name]=definitions
    canonical={name:[asdict(c) for c in values] for name,values in evaluators.items()}
    fingerprint=hashlib.sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest()[:16]
    base=str(payload.get('version','practice-v1')).split(':',1)[0][:120]
    return Policy(base+':'+fingerprint,evaluators)


def dump(policy=DEFAULT):
    return {'version':policy.version,'evaluators':{name:[asdict(c) for c in values] for name,values in policy.evaluators.items()}}


def specification(name, policy=None):
    policy=policy or DEFAULT
    return {'version':policy.version,'criteria':[asdict(c) for c in policy.evaluators[name]],'score_anchors':ANCHORS,
            'unassessed':'Use score=null and claims=[] when not observed. Silence, no drawing or missing discussion is not proof of a gap.'}


def validate_evaluation(name, evaluation: RubricEvaluation, policy=None):
    expected={c.id:c for c in (policy or DEFAULT).evaluators[name]}
    ids=[c.id for c in evaluation.criteria]
    if len(ids)!=len(set(ids)) or set(ids)!=set(expected):
        raise ValueError('Missing, duplicated or unknown rubric criterion')
    for result in evaluation.criteria:
        criterion=expected[result.id]
        if not criterion.scored and result.score is not None:
            raise ValueError('Observable activity is not an ability score')
        if result.score is not None and not result.claims:
            raise ValueError('Scoring requires candidate evidence')
    return expected


def claim_policy(criterion, result, claim):
    if claim.skill_id != criterion.skill_id:
        return 'Claim uses an unknown or inappropriate skill for this criterion'
    if claim.rule not in criterion.rules:
        return 'Claim uses the wrong evidence type for this criterion'
    if not criterion.scored and claim.polarity != 'neutral':
        return 'Activity evidence cannot establish a strength or gap'
    if result.score is not None:
        if claim.polarity=='neutral':
            return 'A scored criterion requires a supported strength or gap'
        if claim.polarity=='gap' and result.score>2:
            return 'Gap contradicts the criterion score'
        if claim.polarity=='strength' and result.score<3:
            return 'Strength contradicts the criterion score'
    if claim.polarity=='gap' and result.score is None:
        return 'A gap needs an observed, scored attempt'
    return None
