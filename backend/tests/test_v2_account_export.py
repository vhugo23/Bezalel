import asyncio
import json
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from app.v2 import account_export as export


class Connection:
    def __init__(self, records=None, user=True):
        self.records = records or {}
        self.user = user
        self.queries = []
        self.transaction_args = None

    @asynccontextmanager
    async def transaction(self, **kwargs):
        self.transaction_args = kwargs
        yield

    async def fetchrow(self, sql, owner):
        assert owner == 'owner-a'
        assert 'password_hash' not in sql and 'deleted_at IS NULL' in sql
        return {'id': owner, 'display_name': 'Synthetic user', 'email': 'a@example.test',
                'created_at': datetime(2026, 10, 11, tzinfo=timezone.utc)} if self.user else None

    async def fetch(self, sql, owner, limit):
        assert owner == 'owner-a' and limit == export.MAX_ROWS + 1
        table = re.search(r'FROM (\w+) r WHERE', sql).group(1)
        assert export.COLLECTIONS[table] in sql
        self.queries.append(sql)
        return [{'record': record} for record in self.records.get(table, [])]


def install(monkeypatch, connection):
    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield connection
    monkeypatch.setattr(export.db, 'pool', AsyncMock(return_value=Pool()))


def test_export_is_owner_filtered_readonly_serializable_and_redacted(monkeypatch):
    connection = Connection({
        'artifacts': [{'id': 'board-a', 'blob_key': '/private/board.png', 'device_id': 'capability',
                       'payload': {'items': [{'type': 'rectangle', 'x': 3}],
                                   'files': {'a': {'dataURL': 'data:image/png;base64,secret'}}}}],
        'memories': [json.dumps({'text': 'Practice tradeoffs', 'external_id': 'provider-id',
                                'data': {'token': 'remote-capability', 'resolved': False}})],
    })
    install(monkeypatch, connection)
    result = asyncio.run(export.export_account('owner-a'))
    assert connection.transaction_args == {'readonly': True, 'isolation': 'repeatable_read'}
    assert len(connection.queries) == len(export.COLLECTIONS)
    encoded = json.dumps(result)
    for secret in ('/private/board.png', 'capability', 'provider-id', 'data:image/png'):
        assert secret not in encoded
    assert result['data']['artifacts'][0]['payload']['items'][0]['x'] == 3
    assert result['data']['memories'][0]['text'] == 'Practice tradeoffs'
    assert result['manifest']['limits']['truncated'] is False
    for query in connection.queries:
        assert query.lstrip().startswith('SELECT')
        assert '$1' in query
    audit_queries = [q for q in connection.queries if 'FROM generation_jobs r' in q or 'FROM work_items r' in q]
    for query in audit_queries:
        assert 'r.request' not in query and 'r.response' not in query and 'r.payload' not in query
        assert 'r.error' not in query and 'r.result' not in query


def test_ownership_predicates_exclude_shared_and_other_user_data():
    assert export.COLLECTIONS['lessons'] == 'r.user_id=$1'
    assert export.COLLECTIONS['memories'] == 'r.owner_id=$1'
    for table in ('artifacts', 'claims', 'session_events', 'evaluator_runs', 'session_reports'):
        assert 's.id=r.session_id AND s.user_id=$1' in export.COLLECTIONS[table]
    assert 't.user_id=$1' in export.COLLECTIONS['scenarios']
    assert 't.user_id=$1' in export.COLLECTIONS['scenario_steps']
    assert 'st.user_id=$1' in export.COLLECTIONS['session_stories']
    assert 'session_devices' not in export.COLLECTIONS
    assert 'accounts' not in export.COLLECTIONS


def test_missing_account_returns_404_without_reading_collections(monkeypatch):
    connection = Connection(user=False)
    install(monkeypatch, connection)
    with pytest.raises(HTTPException) as error:
        asyncio.run(export.export_account('owner-a'))
    assert error.value.status_code == 404
    assert connection.queries == []


@pytest.mark.parametrize('oversize', ['rows', 'bytes'])
def test_large_export_fails_explicitly_instead_of_truncating(monkeypatch, oversize):
    monkeypatch.setattr(export, 'MAX_ROWS', 2)
    monkeypatch.setattr(export, 'MAX_BYTES', 200)
    records = [{}, {}, {}] if oversize == 'rows' else [{'body': 'x' * 300}]
    connection = Connection({'profiles': records})
    install(monkeypatch, connection)
    with pytest.raises(HTTPException) as error:
        asyncio.run(export.export_account('owner-a'))
    assert error.value.status_code == 413
