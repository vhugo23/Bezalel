"""Run browser acceptance against an empty disposable Timescale schema.

Never migrates, seeds, or deletes records in DATABASE_URL. The admin connection
only creates/drops this run's uniquely named schema. All app/provider settings
are overridden in child processes; no paid providers are used.
"""
import asyncio
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from uuid import uuid4

import asyncpg
from app.environment import settings as environment_settings

ROOT = Path(__file__).resolve().parents[2]


def wait_ready(url, process):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('Acceptance server exited; inspect .artifacts/e2e logs')
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(.25)
    raise RuntimeError('Acceptance server did not become ready')


async def seed_fixture(source, schema):
    fixture=json.loads((ROOT/'contracts/e2e-two-step.json').read_text(encoding='utf-8'))
    conn=await asyncpg.connect(source,server_settings={'search_path':schema+',public'})
    try:
        await conn.set_type_codec('jsonb',encoder=json.dumps,decoder=json.loads,schema='pg_catalog')
        async with conn.transaction():
            await conn.execute("INSERT INTO users(id,display_name) VALUES('e2e-generic-user','Synthetic acceptance fixture')")
            await conn.execute("INSERT INTO tracks(id,user_id,domain_id,engine_id,layer,title,source,status) VALUES('e2e-two-step-track','e2e-generic-user','comm','behavioral',3,'Synthetic two-step interview','catalog','ready')")
            await conn.execute("INSERT INTO scenarios(id,track_id,engine_id,engine_version,spec,rubric,validity,validity_report) VALUES('e2e-two-step-scenario','e2e-two-step-track','behavioral','1',$1,$2,'passed',$3)",fixture,fixture['rubric'],{'synthetic':True,'kind':'acceptance_fixture_only','semantic_guarantee':False})
            for step in fixture['steps']:
                await conn.execute("INSERT INTO scenario_steps(scenario_id,idx,title,surface,task,hints,success) VALUES('e2e-two-step-scenario',$1,$2,$3,$4,$5,$6)",step['idx'],step['title'],step['surface'],step['task'],step.get('hints',[]),step['success'])
            for name,look in (('board-first','on_done'),('pause-board','on_pause')):
                tid='e2e-'+name+'-track';sid='e2e-'+name+'-scenario'
                spec={'prompt':'Synthetic board-first system design acceptance fixture.',
                    'steps':[{'idx':0,'title':'Draw the design','surface':'whiteboard','task':'Draw and explain.',
                        'config':{'look':look},'success':{'min_turns':1,'board_review':True}}]}
                await conn.execute("INSERT INTO tracks(id,user_id,domain_id,engine_id,layer,title,source,status) VALUES($1,'e2e-generic-user','sw','conceptual',3,'Synthetic board-first fixture','catalog','ready')",tid)
                await conn.execute("INSERT INTO scenarios(id,track_id,engine_id,engine_version,spec,validity,validity_report) VALUES($1,$2,'conceptual','1',$3,'passed',$4)",sid,tid,spec,{'synthetic':True,'kind':'acceptance_fixture_only'})
            await conn.execute("INSERT INTO sessions(id,user_id,track_id,scenario_id,status) VALUES('e2e-expired-pair-session','e2e-generic-user','e2e-board-first-track','e2e-board-first-scenario','live')")
            await conn.execute("INSERT INTO session_devices(id,session_id,kind,pair_code,expires_at) VALUES('e2e-expired-device','e2e-expired-pair-session','ipad_whiteboard','EXPIRED-CODE',now()-interval '1 minute')")
    finally:
        await conn.close()


async def run():
    settings = environment_settings()
    source = settings.get('E2E_ADMIN_DATABASE_URL') or settings.get('DATABASE_URL')
    if not source:
        raise RuntimeError('Set E2E_ADMIN_DATABASE_URL or DATABASE_URL with CREATE SCHEMA permission')
    name = 'prepcrew_e2e_' + uuid4().hex
    admin = await asyncpg.connect(source)
    children, handles = [], []
    created = False
    output = ROOT / '.artifacts' / 'e2e'
    output.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'DATABASE_URL': source, 'DATABASE_SCHEMA': name, 'V2_DATABASE_SCHEMA': name,
           'DEMO_MODE': 'true', 'LLM_PROVIDER': 'fake', 'VOICE_PROVIDER': 'fake',
           'MEMORY_BACKEND': '', 'GEMINI_API_KEY': '', 'ELEVENLABS_API_KEY': '',
           'BACKBOARD_API_KEY': '', 'PYTHONPATH': str(ROOT / 'backend'),
           'PREPCREW_API_ORIGIN': 'http://127.0.0.1:18000',
           'PREPCREW_WEB_PORT': '15173', 'PREPCREW_E2E_ORIGIN': 'http://127.0.0.1:15173'}
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        for port in (18000, 15173):
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', port))
        await admin.execute(f'CREATE SCHEMA "{name}"')
        created = True
        # stderr may include a DSN on migration errors; keep logs local/ignored.
        with (output / 'migrate.log').open('w', encoding='utf-8') as log:
            result = await asyncio.to_thread(subprocess.run,
                [sys.executable, '-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head'],
                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        if result.returncode:
            raise RuntimeError('Fresh migration failed; inspect .artifacts/e2e/migrate.log')
        from verify_jobs import verify
        await verify(source, name)
        from verify_memory import verify as verify_implicit_memory
        await verify_implicit_memory(source, name)
        await seed_fixture(source,name)
        commands = [
            ([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '18000'], ROOT, 'api'),
            ([shutil.which('node'), str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1'], ROOT / 'frontend', 'web'),
        ]
        for command, cwd, label in commands:
            handle = (output / (label + '.log')).open('w', encoding='utf-8')
            handles.append(handle)
            children.append(subprocess.Popen(command, cwd=cwd, env=env, stdout=handle,
                stderr=subprocess.STDOUT, creationflags=flags))
        await asyncio.to_thread(wait_ready, env['PREPCREW_API_ORIGIN'] + '/api/v2/health', children[0])
        await asyncio.to_thread(wait_ready, env['PREPCREW_E2E_ORIGIN'], children[1])
        command = [shutil.which('node'), str(ROOT / 'frontend/node_modules/@playwright/test/cli.js'), 'test', *sys.argv[1:]]
        with (output / 'browser.log').open('w', encoding='utf-8') as log:
            result = await asyncio.to_thread(subprocess.run, command, cwd=ROOT / 'frontend', env=env,
                stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        print((output / 'browser.log').read_text(encoding='utf-8', errors='replace'))
        return result.returncode
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    await asyncio.to_thread(child.wait, timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    await asyncio.to_thread(child.wait)
        for handle in handles:
            handle.close()
        if created:
            await admin.execute(f'DROP SCHEMA "{name}" CASCADE')
        await admin.close()
        print('Acceptance environment stopped; disposable schema removed.' if created else 'No test schema was created.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    try:
        raise SystemExit(asyncio.run(run()))
    except Exception as error:
        print(type(error).__name__ + ': acceptance setup failed; inspect local logs.', file=sys.stderr)
        raise SystemExit(1)
