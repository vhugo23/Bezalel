"""Short-lived, single-use capabilities for a direct backend WebSocket."""
import hashlib
import re
import secrets
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel
from . import db

TTL_SECONDS = 45
MAX_OUTSTANDING = 20
Channel = Literal['events', 'voice']


class SocketTicketInput(BaseModel):
    channel: Channel


class SocketTicket(BaseModel):
    token: str
    expires_in_seconds: int = TTL_SECONDS


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue(user_id: str, auth_token_hash: str, sid: str, channel: Channel) -> SocketTicket:
    if channel not in ('events', 'voice'):
        raise HTTPException(422, 'Unsupported socket channel')
    async with (await db.pool()).acquire() as connection:
        async with connection.transaction():
            # Serializing issuance on the parent authentication session makes the
            # outstanding-ticket limit hold even for concurrent requests.
            owner = await connection.fetchrow('''SELECT a.token_hash
                FROM auth_sessions a JOIN users u ON u.id=a.user_id
                JOIN sessions s ON s.user_id=a.user_id
                WHERE a.token_hash=$1 AND a.user_id=$2 AND a.expires_at>now()
                  AND u.deleted_at IS NULL AND s.id=$3
                FOR UPDATE OF a''', auth_token_hash, user_id, sid)
            if not owner:
                raise HTTPException(404, 'Session not found')
            await connection.execute('''DELETE FROM socket_tickets
                WHERE auth_token_hash=$1 AND expires_at<=now()''', auth_token_hash)
            count = await connection.fetchval(
                'SELECT count(*) FROM socket_tickets WHERE auth_token_hash=$1', auth_token_hash)
            if count >= MAX_OUTSTANDING:
                raise HTTPException(429, 'Too many pending socket connections; try again shortly.')
            token = secrets.token_urlsafe(32)
            await connection.execute('''INSERT INTO socket_tickets
                (token_hash,auth_token_hash,session_id,channel,expires_at)
                VALUES($1,$2,$3,$4,now()+$5*interval '1 second')''',
                _digest(token), auth_token_hash, sid, channel, TTL_SECONDS)
            return SocketTicket(token=token)


async def consume(token: str, sid: str, channel: Channel) -> str | None:
    if channel not in ('events', 'voice') or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        return None
    # DELETE is the claim operation: concurrent upgrades cannot reuse a ticket.
    # Wrong scopes do not consume a still-valid ticket for its intended socket.
    row = await db.one('''DELETE FROM socket_tickets t USING auth_sessions a, sessions s, users u
        WHERE t.token_hash=$1 AND t.session_id=$2 AND t.channel=$3 AND t.expires_at>now()
          AND a.token_hash=t.auth_token_hash AND a.expires_at>now()
          AND s.id=t.session_id AND s.user_id=a.user_id
          AND u.id=a.user_id AND u.deleted_at IS NULL
        RETURNING t.auth_token_hash''', _digest(token), sid, channel)
    return row['auth_token_hash'] if row else None
