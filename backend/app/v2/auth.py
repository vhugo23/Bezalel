"""Opaque server sessions and ownership at the HTTP/WebSocket boundary.

No request-supplied user ID grants access. Pairing remains a deliberately narrow
device capability: it cannot read conversation turns or obtain an account cookie.
"""
import asyncio
import hashlib
import os
import re
import secrets
from contextlib import suppress
from urllib.parse import unquote

import asyncpg
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse

from app import config
from . import db

COOKIE='prepcrew_session'
TTL=60*60*24*14
SOCKET_CHECK_SECONDS=15
hasher=PasswordHasher()
hash_slots=asyncio.Semaphore(2)
# Verification of a nonexistent account does comparable password work.
DUMMY_HASH=hasher.hash(secrets.token_urlsafe(32))
router=APIRouter(prefix='/api/v2/auth',tags=['Accounts'])


class Account(BaseModel):
    id: str
    name: str
    email: str


class AuthState(BaseModel):
    enabled: bool=True
    user: Account | None=None


class Credentials(BaseModel):
    email: str=Field(min_length=3,max_length=254)
    password: str=Field(min_length=12,max_length=256)

    @field_validator('email')
    @classmethod
    def valid_email(cls,value):
        value=value.strip().lower()
        if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}",value):
            raise ValueError('Enter a valid email address.')
        return value


class Registration(Credentials):
    name: str=Field(min_length=1,max_length=80)

    @field_validator('name')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():raise ValueError('Enter your name.')
        return value.strip()


def enabled():
    safe_test=(config.V2_AUTH_TEST_BYPASS and
        config.V2_DATABASE_SCHEMA.startswith('prepcrew_e2e_') and
        os.getenv('DEMO_MODE')=='true' and
        not any((config.GEMINI_API_KEY,config.ELEVENLABS_API_KEY,config.BACKBOARD_API_KEY)))
    return not safe_test


def digest(value):return hashlib.sha256(value.encode()).hexdigest()


def trusted_origins():
    origins={o.rstrip('/') for o in config.CORS_ORIGINS}
    if config.PUBLIC_BASE_URL:origins.add(config.PUBLIC_BASE_URL.rstrip('/'))
    # Browser acceptance uses an isolated schema and a fixed local frontend.
    if config.V2_DATABASE_SCHEMA.startswith('prepcrew_e2e_'):
        origins.add('http://127.0.0.1:15173')
    return origins


def check_origin(connection):
    origin=connection.headers.get('origin')
    if origin and origin not in trusted_origins():
        raise HTTPException(403,'This origin is not allowed.')
    if not origin and connection.headers.get('sec-fetch-site') in {'cross-site','same-site'}:
        # Cross-origin navigation/image requests can omit Origin, including GETs
        # that resume a review or synthesize speech. Explicit trusted CORS clients
        # send Origin; same-origin app navigation and nonbrowser clients still work.
        raise HTTPException(403,'Open this resource from your workspace.')


async def current(connection):
    token=connection.cookies.get(COOKIE,'')
    if not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):return None
    return await db.one('''SELECT a.user_id AS id,a.email,coalesce(u.display_name,'') AS name
        FROM auth_sessions s JOIN accounts a ON a.user_id=s.user_id
        JOIN users u ON u.id=a.user_id
        WHERE s.token_hash=$1 AND s.expires_at>now() AND u.deleted_at IS NULL''',digest(token))


async def require_owner(user_id,table,resource_id):
    # Only fixed identifiers supplied by our route policy, never user input.
    if table not in {'sessions','plans','tracks','source_documents','work_items','artifacts'}:
        raise RuntimeError('Unknown ownership policy')
    if table=='artifacts':
        sql='SELECT s.user_id FROM artifacts a JOIN sessions s ON s.id=a.session_id WHERE a.id=$1'
    else:sql=f'SELECT user_id FROM {table} WHERE id=$1'
    row=await db.one(sql,resource_id)
    if not row or row['user_id']!=user_id:raise HTTPException(404,'Resource not found.')


def identity(request,user_id):
    if not enabled():return user_id
    actor=request.state.account['id']
    if user_id!=actor:raise HTTPException(403,'Use your signed-in account.')
    return actor


async def body_owner(request,table,resource_id):
    if enabled():await require_owner(request.state.account['id'],table,resource_id)


async def limit(request,email):
    # Atomic fixed windows shared by all workers. No passwords or raw addresses.
    address=request.client.host if request.client else 'unknown'
    async with (await db.pool()).acquire() as conn,conn.transaction():
        await conn.execute('DELETE FROM auth_attempts WHERE expires_at<=now()')
        for key,maximum in (('ip:'+address,40),('email:'+email,12)):
            attempts=await conn.fetchval('''INSERT INTO auth_attempts(key,attempts,expires_at)
                VALUES($1,1,now()+interval '15 minutes') ON CONFLICT(key) DO UPDATE
                SET attempts=auth_attempts.attempts+1 RETURNING attempts''',digest(key))
            # Commit exceeded attempts rather than rolling them back on HTTPException.
            if attempts>maximum:return False
    return True


async def password_work(function,*args):
    # Memory/CPU work off the event loop; fail quickly instead of an unbounded queue.
    try:await asyncio.wait_for(hash_slots.acquire(),timeout=.1)
    except TimeoutError:raise HTTPException(429,'Sign-in is busy. Try again shortly.')
    task=asyncio.create_task(asyncio.to_thread(function,*args))
    try:return await asyncio.shield(task)
    except asyncio.CancelledError:
        # Cancelling to_thread does not stop its CPU work. Keep its slot until it
        # actually finishes so disconnected clients cannot defeat the bound.
        with suppress(Exception):await task
        raise
    finally:hash_slots.release()


async def issue(response,user_id,previous_token=''):
    token=secrets.token_urlsafe(32)
    async with (await db.pool()).acquire() as conn,conn.transaction():
        account=await conn.fetchrow('''SELECT a.user_id FROM accounts a
            JOIN users u ON u.id=a.user_id WHERE a.user_id=$1 AND u.deleted_at IS NULL
            FOR UPDATE OF a,u''',user_id)
        if not account:raise HTTPException(401,'Sign in to open your workspace.')
        await conn.execute('DELETE FROM auth_sessions WHERE expires_at<=now()')
        if previous_token:
            await conn.execute('DELETE FROM auth_sessions WHERE token_hash=$1',digest(previous_token))
        # Bound active sessions per account without mutating another user's sessions.
        await conn.execute('''DELETE FROM auth_sessions WHERE token_hash IN
            (SELECT token_hash FROM auth_sessions WHERE user_id=$1
             ORDER BY created_at DESC OFFSET 9)''',user_id)
        await conn.execute("INSERT INTO auth_sessions(token_hash,user_id,expires_at) VALUES($1,$2,now()+interval '14 days')",digest(token),user_id)
    response.set_cookie(COOKIE,token,max_age=TTL,httponly=True,secure=config.AUTH_COOKIE_SECURE,samesite='lax',path='/')
    response.headers['Cache-Control']='no-store'


@router.get('/me',response_model=AuthState)
async def me(request:Request,response:Response):
    response.headers['Cache-Control']='no-store'
    row=await current(request) if enabled() else None
    return AuthState(enabled=enabled(),user=Account(**dict(row)) if row else None)


@router.post('/register',response_model=AuthState,status_code=201)
async def register(body:Registration,request:Request,response:Response):
    if not await limit(request,body.email):raise HTTPException(429,'Too many attempts. Try again in 15 minutes.')
    hashed=await password_work(hasher.hash,body.password)
    user_id=secrets.token_hex(16)
    try:
        async with (await db.pool()).acquire() as conn,conn.transaction():
            # Existing unauthenticated workspaces are not claimed by supplying an ID/email.
            await conn.execute('INSERT INTO users(id,display_name) VALUES($1,$2)',user_id,body.name)
            await conn.execute('INSERT INTO accounts(user_id,email,password_hash) VALUES($1,$2,$3)',user_id,body.email,hashed)
    except asyncpg.UniqueViolationError:raise HTTPException(409,'Could not create this account. Try signing in.')
    await issue(response,user_id,request.cookies.get(COOKIE,''))
    return AuthState(user=Account(id=user_id,name=body.name,email=body.email))


@router.post('/login',response_model=AuthState)
async def login(body:Credentials,request:Request,response:Response):
    if not await limit(request,body.email):raise HTTPException(429,'Too many attempts. Try again in 15 minutes.')
    row=await db.one('''SELECT a.*,coalesce(u.display_name,'') AS name FROM accounts a
        JOIN users u ON u.id=a.user_id WHERE a.email=$1 AND u.deleted_at IS NULL''',body.email)
    try:valid=await password_work(hasher.verify,row['password_hash'] if row else DUMMY_HASH,body.password)
    except (VerificationError,InvalidHashError):valid=False
    if not row or not valid:raise HTTPException(401,'Email or password is incorrect.')
    if hasher.check_needs_rehash(row['password_hash']):
        hashed=await password_work(hasher.hash,body.password)
        await db.execute('UPDATE accounts SET password_hash=$2 WHERE user_id=$1',row['user_id'],hashed)
    await issue(response,row['user_id'],request.cookies.get(COOKIE,''))
    return AuthState(user=Account(id=row['user_id'],name=row['name'],email=row['email']))


@router.post('/logout',response_model=AuthState)
async def logout(request:Request,response:Response):
    await db.execute('DELETE FROM auth_sessions WHERE token_hash=$1',digest(request.cookies.get(COOKIE,'')))
    response.delete_cookie(COOKIE,path='/',httponly=True,secure=config.AUTH_COOKIE_SECURE,samesite='lax')
    response.headers['Cache-Control']='no-store'
    return AuthState(enabled=enabled())


class AccessBoundary:
    """Protect all v2 resources, including raw images/audio and both owner sockets.

    HTTP bodies are checked separately by routes after typed validation. Socket
    lifetimes revalidate every 15 seconds so logout/expiry closes an idle voice
    connection too; the provider relay's finally block releases its resources.
    """
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type'] not in {'http','websocket'}:
            return await self.app(scope,receive,send)
        path=scope['path'];socket=scope['type']=='websocket'
        legacy=(path.startswith('/api/') and not path.startswith('/api/v2/')) or (path.startswith('/ws/') and not path.startswith('/ws/v2/'))
        if legacy and path!='/api/health' and not config.LEGACY_API_ENABLED:
            if socket:await send({'type':'websocket.close','code':4404})
            else:await JSONResponse({'detail':'Legacy API is disabled.'},status_code=404)(scope,receive,send)
            return
        v2=path.startswith('/ws/v2/') if socket else path.startswith('/api/v2/')
        if not v2 or not enabled():return await self.app(scope,receive,send)
        connection=HTTPConnection(scope)
        try:
            check_origin(connection)
            if not socket and scope['method'] not in {'GET','HEAD','OPTIONS'}:
                # Custom header + exact-origin CORS prevents simple HTML form CSRF,
                # including multipart/binary uploads and login CSRF.
                if connection.headers.get('x-prepcrew-request')!='1':
                    raise HTTPException(403,'Missing request protection header.')
            public=path.startswith('/api/v2/auth/') or path=='/api/v2/health' or path.startswith('/ws/v2/pair/') or (not socket and scope['method']=='OPTIONS')
            if public:return await self.app(scope,receive,send)
            account=await current(connection)
            if not account:raise HTTPException(401,'Sign in to open your workspace.')
            scope.setdefault('state',{})['account']=dict(account)
            pattern=r'^/(?:api|ws)/v2/(sessions|voice|plans|sources|jobs|artifacts)/([^/]+)(?:/|$)'
            match=re.match(pattern,path)
            collection_action=(not socket and scope['method']=='POST' and
                path in {'/api/v2/plans/jobs','/api/v2/sources/upload','/api/v2/sources/github'})
            if match and not collection_action:
                table={'voice':'sessions','sources':'source_documents','jobs':'work_items'}.get(match[1],match[1])
                await require_owner(account['id'],table,unquote(match[2]))
            match=re.match(r'^/api/v2/users/([^/]+)/',path)
            if match and unquote(match[1])!=account['id']:raise HTTPException(404,'Resource not found.')
        except HTTPException as error:
            if socket:await send({'type':'websocket.close','code':4401 if error.status_code==401 else 4404})
            else:await JSONResponse({'detail':error.detail},status_code=error.status_code,headers={'Cache-Control':'no-store'})(scope,receive,send)
            return
        if not socket:
            async def private_send(message):
                if message['type']=='http.response.start':
                    message['headers']=[(k,v) for k,v in message.get('headers',[]) if k.lower()!=b'cache-control']+[(b'cache-control',b'no-store')]
                await send(message)
            return await self.app(scope,receive,private_send)
        closed=False
        async def monitor():
            nonlocal closed
            while True:
                await asyncio.sleep(SOCKET_CHECK_SECONDS)
                if not await current(connection):
                    closed=True
                    await send({'type':'websocket.close','code':4401})
                    return
        async def guarded_send(message):
            if not closed:await send(message)
        task=asyncio.create_task(self.app(scope,receive,guarded_send))
        watcher=asyncio.create_task(monitor())
        try:
            done,_=await asyncio.wait({task,watcher},return_when=asyncio.FIRST_COMPLETED)
            for completed in done:completed.result()
        finally:
            for pending in (task,watcher):
                if not pending.done():pending.cancel()
            await asyncio.gather(task,watcher,return_exceptions=True)
