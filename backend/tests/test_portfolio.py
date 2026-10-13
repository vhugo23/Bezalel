"""Guard the portable install and optional-service boundaries."""
import asyncio
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest
from app import config
from app.postgres_schema import portable_schema
from app.v2 import memory, routes, service, assessment, pi_lab, devices


def test_frozen_schema_renders_without_timescale_statements():
    source = Path(__file__).parents[1] / 'migrations/sql/001_v23.sql'
    sql = portable_schema(source.read_text(encoding='utf-8'))
    statements = '\n'.join(line for line in sql.splitlines() if not line.lstrip().startswith('--'))
    for extension_only in ('timescaledb', 'create_hypertable', 'time_bucket', 'add_continuous_aggregate_policy'):
        assert extension_only not in statements
    assert 'CREATE OR REPLACE VIEW mastery_hourly' in sql
    assert 'array_agg(score ORDER BY ts DESC)' in sql
    assert 'CREATE TABLE IF NOT EXISTS session_events' in sql
    assert "('infra.pi_site'" in sql


@pytest.mark.parametrize('backend,expected', [('', False), ('postgres', False), ('memory', False), ('backboard', True)])
def test_backboard_requires_explicit_opt_in_even_with_a_key(monkeypatch, backend, expected):
    monkeypatch.setattr(config, 'BACKBOARD_API_KEY', 'synthetic-key')
    monkeypatch.setattr(config, 'MEMORY_BACKEND', backend)
    monkeypatch.setattr(memory, 'DEMO', False)
    assert memory.enabled() is expected


def test_speech_without_optional_provider_uses_browser_after_event_lookup(monkeypatch):
    monkeypatch.setattr(routes, 'DEMO', False)
    monkeypatch.setattr(config, 'ELEVENLABS_API_KEY', '')
    monkeypatch.setattr(routes.s, 'require_session', AsyncMock())
    monkeypatch.setattr(routes.db, 'one', AsyncMock(return_value={'payload': {'text': 'Saved reply'}}))
    response = asyncio.run(routes.speech('session', 2))
    assert response.status_code == 204
    assert response.headers['X-PrepCrew-Speech-Fallback'] == 'browser'


def test_portable_metrics_never_query_timescale_catalogs(monkeypatch):
    monkeypatch.setattr(routes.s, 'require_session', AsyncMock(return_value={'user_id': 'owner'}))
    monkeypatch.setattr(routes.db, 'one', AsyncMock(return_value=None))
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(routes.db, 'fetch', fetch)
    result = asyncio.run(routes.metrics('session'))
    assert result.hypertables == [] and result.aggregates == ['mastery_hourly', 'latency_1m']
    assert all('timescaledb_information' not in call.args[0] for call in fetch.call_args_list)


def test_local_launcher_overrides_cloud_database_and_provider_settings(monkeypatch):
    path = Path(__file__).parents[1] / 'scripts/run_portfolio.py'
    spec = importlib.util.spec_from_file_location('portfolio_launcher', path)
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    monkeypatch.setattr(launcher, 'settings', lambda: {
        'DATABASE_URL': 'postgresql://synthetic-cloud/production',
        'GEMINI_API_KEY': 'synthetic-key', 'ELEVENLABS_API_KEY': 'synthetic-key',
        'BACKBOARD_API_KEY': 'synthetic-key', 'MEMORY_BACKEND': 'backboard'})
    env = launcher.environment()
    assert '@127.0.0.1:15432/prepcrew' in env['DATABASE_URL']
    assert env['DEMO_MODE'] == 'true' and env['MEMORY_BACKEND'] == 'postgres'
    assert not any(env[key] for key in ('GEMINI_API_KEY','ELEVENLABS_API_KEY','BACKBOARD_API_KEY'))


def test_scripted_report_does_not_invent_queued_evaluators(monkeypatch):
    monkeypatch.setattr(service, 'require_session', AsyncMock(return_value={'status':'graded'}))
    monkeypatch.setattr(service.engine, 'context', AsyncMock(return_value={**pi_lab.definition(), 'engine_id':'linux_fault'}))
    monkeypatch.setattr(assessment, 'latest_runs', AsyncMock(return_value=[]))
    monkeypatch.setattr(service.db, 'fetch', AsyncMock(return_value=[]))
    monkeypatch.setattr(service.db, 'one', AsyncMock(return_value={
        'report': {'scripted_walkthrough': {'scripted': True}, 'rubric_version':'fixture'},
        'stats': {'scripted_demo': True}, 'overall': None}))
    report = asyncio.run(service.report('session'))
    assert report.demo and not report.evaluators and not report.scores
    assert report.next_gap is None and report.overall is None


def test_pairing_resends_annotations_that_arrive_for_the_same_artifact():
    pending = SimpleNamespace(model_dump=lambda **_: {'artifact_id':'same', 'annotations':[]})
    ready = SimpleNamespace(model_dump=lambda **_: {'artifact_id':'same', 'annotations':[{'id':'mark'}]})
    assert devices.review_key(pending) != devices.review_key(ready)
    assert devices.review_key(ready) == devices.review_key(ready)
    assert devices.review_key(None) is None
