import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
import pytest
from app.v2 import realtime as rt, service, generation
from app.v2.models import Event, Reply, TurnResult


def event(seq=1,actor='candidate',text='Can we support bursts?'):
    return Event(session_id='s',seq=seq,actor=actor,kind='turn',step=0,payload={'text':text},ts=datetime.now(timezone.utc))


@pytest.fixture
def conversation(monkeypatch):
    send=AsyncMock()
    monkeypatch.setattr(rt.s,'require_session',AsyncMock(return_value={'status':'live','step':0}))
    monkeypatch.setattr(rt.s,'log',AsyncMock(return_value=event()))
    monkeypatch.setattr(rt.s,'record_candidate',AsyncMock(return_value=event()))
    monkeypatch.setattr(rt.s,'acknowledge_reply',AsyncMock(return_value='advance'))
    return rt.Conversation('s',send),send


@pytest.mark.parametrize('text',['','uh','hmm','[um]','[cough]','(background noise)'])
def test_non_speech_does_not_interrupt_or_become_evidence(conversation,text):
    c,send=conversation;c.playing=7
    asyncio.run(c.transcript(text,True))
    assert c.playing==7
    rt.s.record_candidate.assert_not_called()
    send.assert_not_called()


def test_playback_echo_is_filtered_but_new_words_interrupt(conversation):
    c,send=conversation;c.playing=7;c.last_dana='What traffic volume should we handle?'
    async def check():
        await c.transcript('What traffic volume')
        assert c.playing==7
        await c.transcript('Wait, I meant requests per user')
        assert c.playing is None
        await c.transcript('Wait, I meant requests per user')
    asyncio.run(check())
    assert [x.args[0]['type'] for x in send.call_args_list]==['interrupt','partial']
    rt.s.log.assert_awaited_once()


def test_barge_in_cancels_pending_generation_and_never_delivers_stale_reply(conversation,monkeypatch):
    c,send=conversation
    async def check():
        started=asyncio.Event();cancelled=asyncio.Event()
        async def slow(*_):
            started.set()
            try:await asyncio.Future()
            finally:cancelled.set()
        monkeypatch.setattr(rt.s,'respond',slow)
        await c.submit('My first idea is Redis.')
        await asyncio.wait_for(started.wait(),2)
        await c.transcript('Actually, I would change that')
        assert cancelled.is_set()
        assert not any(x.args[0]['type']=='reply' for x in send.call_args_list)
        await c.close()
    asyncio.run(check())


def test_only_current_completed_playback_can_advance(conversation):
    c,send=conversation;c.playing=7;c.revision=3
    async def check():
        await c.playback_done(7,2)
        rt.s.acknowledge_reply.assert_not_called()
        await c.playback_done(6,3)
        rt.s.acknowledge_reply.assert_not_called()
        await c.playback_done(7,3)
        rt.s.acknowledge_reply.assert_awaited_once_with('s',7)
    asyncio.run(check())


def test_muted_and_discarded_segments_cannot_become_evidence(conversation):
    c,_=conversation
    async def check():
        c.muted=True;await c.transcript('Background conversation',True)
        c.muted=False;c.discard_segment=True;await c.transcript('Tail from before mute',True)
    asyncio.run(check())
    rt.s.record_candidate.assert_not_called()


def test_model_cancellation_closes_its_audit_job(monkeypatch):
    monkeypatch.setattr(generation,'DEMO',True)
    calls=[]
    async def execute(sql,*args):
        calls.append((sql,args))
        if "status=$2" in sql:raise asyncio.CancelledError()
    monkeypatch.setattr(generation.db,'execute',execute)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(generation.generate('interviewer','s','prompt',Reply,{'text':'Hello'}))
    assert any("stage='Cancelled'" in sql for sql,_ in calls)


@pytest.mark.parametrize('action,step,count,looked,text,expected',[
    ('advance',0,1,False,'hello','continue'),
    ('advance',0,2,False,'ready to draw','advance'),
    ('advance',1,3,False,'ready','continue'),
    ('advance',1,3,True,'ready','advance'),
    ('look',1,1,False,'I am not done','continue'),
    ('look',1,1,False,'Take a look at my board','look'),
    ('finish',0,8,False,'done','continue'),
    ('finish',2,1,True,'done','continue'),
    ('finish',2,2,True,'I explained the trade-off','finish'),
])
def test_agent_progression_guards(action,step,count,looked,text,expected):
    assert service.allowed_action(action,step,count,looked,text)==expected


@pytest.mark.parametrize('latest,expected',[(1,['look','continue']),(8,['continue','continue'])])
def test_reply_ack_is_idempotent_and_rejects_interrupted_reply(monkeypatch,latest,expected):
    saved=[]
    class Context:
        def __init__(self,value):self.value=value
        async def __aenter__(self):return self.value
        async def __aexit__(self,*_):pass
    class Connection:
        def transaction(self):return Context(None)
        async def fetchrow(self,sql,*_):
            if 'FROM sessions' in sql:return {'status':'live','step':1}
            return {'step':1,'payload':{'action':'look'}}
        async def fetchval(self,sql,*_):
            return latest if 'max(seq)' in sql else bool(saved)
    class Pool:
        def acquire(self):return Context(Connection())
    async def log(*args):saved.append(args)
    monkeypatch.setattr(service.db,'pool',AsyncMock(return_value=Pool()))
    monkeypatch.setattr(service,'log',log)
    async def check():
        return [await service.acknowledge_reply('s',7),await service.acknowledge_reply('s',7)]
    assert asyncio.run(check())==expected
    assert len(saved)==(1 if latest<7 else 0)


@pytest.mark.parametrize('text,question,look',[
    ('Uh, so what do you think about what I got going on here?', True, True),
    ('Um, what do you think about my design', True, True),
    ('How does this look?', True, True),
    ('What do you think about Redis?', True, False),
    ('I am not ready for your feedback', False, False),
    ('I am drawing a load balancer', False, False),
])
def test_whiteboard_spoken_intent(text,question,look):
    assert service.is_question(text)==question
    assert service.board_look_requested(text)==look


def test_adjacent_stt_fragments_preserve_question_context():
    from datetime import timedelta
    a=event(190,text='Uh, so what do you think about what I got')
    b=event(191,text='going on here?')
    b.ts=a.ts+timedelta(seconds=2)
    text=service.candidate_utterance([a,b],b)
    assert service.board_look_requested(text)
    boundary=event(190,actor='interviewer',text='Please continue')
    assert service.candidate_utterance([boundary,b],b)==b.payload['text']
    b.ts=a.ts+timedelta(seconds=20)
    assert service.candidate_utterance([a,b],b)==b.payload['text']


@pytest.mark.parametrize('reply_text,expected_source',[
    ('Yes, I can hear you.','gemini'),
    ('','authored'),
])
def test_listen_action_never_swallows_answer_to_question(monkeypatch,reply_text,expected_source):
    candidate=event(text='You guys can hear me?');candidate.step=1
    monkeypatch.setattr(service,'events',AsyncMock(return_value=[candidate]))
    monkeypatch.setattr(service.db,'one',AsyncMock(return_value=None))
    monkeypatch.setattr(service,'generate',AsyncMock(return_value=(Reply(text=reply_text,action='listen'),'job','gemini')))
    class Context:
        def __init__(self,value):self.value=value
        async def __aenter__(self):return self.value
        async def __aexit__(self,*_):pass
    class Connection:
        def transaction(self):return Context(None)
        async def fetchrow(self,*_):return {'status':'live','step':1}
        async def fetchval(self,*_):return candidate.seq
    class Pool:
        def acquire(self):return Context(Connection())
    monkeypatch.setattr(service.db,'pool',AsyncMock(return_value=Pool()))
    logged=AsyncMock(return_value=event(2,'interviewer',reply_text))
    monkeypatch.setattr(service,'log',logged)
    result=asyncio.run(service.respond('s',candidate))
    assert len(result.events)==1
    assert result.source==expected_source
    payload=logged.call_args.args[4]
    assert payload['text']
    assert payload['action']=='continue'
