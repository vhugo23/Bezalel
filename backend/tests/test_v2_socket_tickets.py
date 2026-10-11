import asyncio
import hashlib
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.v2 import socket_tickets as tickets


class Connection:
    def __init__(self, owner=True, count=0):
        self.fetchrow = AsyncMock(return_value={'token_hash': 'auth-hash'} if owner else None)
        self.fetchval = AsyncMock(return_value=count)
        self.execute = AsyncMock()
        self.in_transaction = False

    @asynccontextmanager
    async def transaction(self):
        self.in_transaction = True
        yield
        self.in_transaction = False


def install(monkeypatch, connection):
    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield connection
    monkeypatch.setattr(tickets.db, 'pool', AsyncMock(return_value=Pool()))


def test_issue_stores_only_hash_and_locks_auth_session_before_enforcing_limit(monkeypatch):
    connection = Connection()
    install(monkeypatch, connection)
    ticket = asyncio.run(tickets.issue('owner', 'auth-hash', 'session-a', 'voice'))
    assert ticket.expires_in_seconds == 45
    assert len(ticket.token) == 43
    sql, auth_hash, user, sid = connection.fetchrow.call_args.args
    assert 'FOR UPDATE OF a' in sql
    assert 'a.expires_at>now()' in sql and 'u.deleted_at IS NULL' in sql
    assert 's.user_id=a.user_id' in sql
    assert (auth_hash, user, sid) == ('auth-hash', 'owner', 'session-a')
    cleanup, insert = connection.execute.call_args_list
    assert 'expires_at<=now()' in cleanup.args[0]
    assert insert.args[1:] == (hashlib.sha256(ticket.token.encode()).hexdigest(),
                              'auth-hash', 'session-a', 'voice', 45)
    assert ticket.token not in str(connection.execute.call_args_list)


@pytest.mark.parametrize('owner,count,expected', [(False, 0, 404), (True, 20, 429)])
def test_issue_rejects_foreign_or_expired_auth_and_bounds_outstanding(monkeypatch, owner, count, expected):
    connection = Connection(owner=owner, count=count)
    install(monkeypatch, connection)
    with pytest.raises(HTTPException) as error:
        asyncio.run(tickets.issue('owner', 'auth-hash', 'session-a', 'events'))
    assert error.value.status_code == expected
    assert not any('INSERT' in call.args[0] for call in connection.execute.call_args_list)


def test_consume_atomically_deletes_only_matching_live_owned_ticket(monkeypatch):
    query = AsyncMock(side_effect=[{'auth_token_hash': 'auth-hash'}, None])
    monkeypatch.setattr(tickets.db, 'one', query)
    token = 'a' * 43
    assert asyncio.run(tickets.consume(token, 'session-a', 'voice')) == 'auth-hash'
    assert asyncio.run(tickets.consume(token, 'session-a', 'voice')) is None
    sql, hashed, sid, channel = query.call_args.args
    assert hashed == hashlib.sha256(token.encode()).hexdigest()
    assert (sid, channel) == ('session-a', 'voice')
    for condition in ('DELETE FROM socket_tickets', 't.session_id=$2', 't.channel=$3',
                      't.expires_at>now()', 'a.expires_at>now()', 's.user_id=a.user_id',
                      'u.deleted_at IS NULL', 'RETURNING t.auth_token_hash'):
        assert condition in sql


@pytest.mark.parametrize('token,channel', [('', 'voice'), ('bad token', 'voice'),
                                          ('a' * 44, 'voice'), ('a' * 43, 'admin')])
def test_invalid_ticket_or_channel_never_queries_database(monkeypatch, token, channel):
    query = AsyncMock()
    monkeypatch.setattr(tickets.db, 'one', query)
    assert asyncio.run(tickets.consume(token, 'session-a', channel)) is None
    query.assert_not_called()


def test_channel_schema_rejects_unscoped_connections():
    with pytest.raises(ValidationError):
        tickets.SocketTicketInput(channel='admin')
    assert tickets.SocketTicketInput(channel='events').channel == 'events'
