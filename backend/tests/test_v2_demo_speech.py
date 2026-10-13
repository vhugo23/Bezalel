import asyncio
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app import config
from app.v2 import demo_speech as speech, demo_autoplay, db, voice


def test_role_voices_are_distinct_and_only_authored_text_is_allowed(monkeypatch):
    monkeypatch.setattr(config,'ELEVENLABS_VOICE_ID','dana-voice')
    monkeypatch.setenv('ELEVENLABS_DEMO_CANDIDATE_VOICE_ID','candidate-voice')
    assert speech.voice_for('candidate')=='candidate-voice'
    assert speech.voice_for('interviewer')=='dana-voice'
    assert speech.allowed('candidate',next(iter(demo_autoplay.CANDIDATE_UTTERANCES)))
    assert not speech.allowed('candidate','arbitrary text requesting paid synthesis')
    assert not speech.allowed('interviewer','arbitrary personal account content')


def test_cache_reuses_clip_across_sessions_without_another_provider_call(monkeypatch,tmp_path):
    monkeypatch.setattr(speech,'CACHE_DIRECTORY',tmp_path)
    monkeypatch.setattr(config,'ELEVENLABS_VOICE_ID','dana-voice')
    monkeypatch.setenv('ELEVENLABS_DEMO_CANDIDATE_VOICE_ID','candidate-voice')
    monkeypatch.setattr(demo_autoplay,'supported',AsyncMock(return_value=({'engine_state':{'scripted_demo':True}},{})))
    text=demo_autoplay.DEMO_OPENINGS['conceptual']
    monkeypatch.setattr(db,'one',AsyncMock(return_value={'actor':'interviewer','payload':{'text':text}}))
    async def chunks():yield b'synthetic-mp3'
    speak=AsyncMock(side_effect=lambda *args,**kwargs:StreamingResponse(chunks(),media_type='audio/mpeg'))
    monkeypatch.setattr(voice,'speak',speak)
    async def run():
        first=await speech.speech('first',1);second=await speech.speech('second',2)
        assert first.body==second.body==b'synthetic-mp3'
        assert first.headers['X-PrepCrew-Speech-Cache']=='miss'
        assert second.headers['X-PrepCrew-Speech-Cache']=='hit'
    asyncio.run(run());speak.assert_awaited_once_with('first',text,voice_id='dana-voice')


def test_quota_fallback_header_is_preserved_and_failed_clip_not_cached(monkeypatch,tmp_path):
    monkeypatch.setattr(speech,'CACHE_DIRECTORY',tmp_path)
    monkeypatch.setattr(config,'ELEVENLABS_VOICE_ID','dana-voice')
    monkeypatch.setenv('ELEVENLABS_DEMO_CANDIDATE_VOICE_ID','candidate-voice')
    monkeypatch.setattr(demo_autoplay,'supported',AsyncMock(return_value=({'engine_state':{'scripted_demo':True}},{})))
    monkeypatch.setattr(db,'one',AsyncMock(return_value={'actor':'candidate','payload':{'text':next(iter(demo_autoplay.CANDIDATE_UTTERANCES))}}))
    monkeypatch.setattr(voice,'speak',AsyncMock(side_effect=voice.provider_error(402)))
    with pytest.raises(HTTPException) as error:asyncio.run(speech.speech('session',1))
    assert error.value.headers['X-PrepCrew-Speech-Fallback']=='quota'
    assert not list(tmp_path.iterdir())
