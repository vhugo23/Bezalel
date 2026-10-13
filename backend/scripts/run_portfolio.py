"""Run a local portfolio demo without inheriting cloud database/provider settings."""
import argparse
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from app.environment import settings


def environment(live=False):
    env = settings()
    # Always use the dedicated local DB. Existing root .env may target production.
    env.update(DATABASE_URL='postgresql://prepcrew:prepcrew_local@127.0.0.1:15432/prepcrew',
               V2_DATABASE_SCHEMA='prepcrew', DATABASE_TIMESCALE='false',
               PYTHONPATH=str(ROOT / 'backend'), MEMORY_BACKEND='postgres',
               BACKBOARD_API_KEY='', LEGACY_API_ENABLED='false',
               V2_AUTH_TEST_BYPASS='false', AUTH_COOKIE_SECURE='false', PUBLIC_BASE_URL='',
               DEMO_MODE='false' if live else 'true',
               PREPCREW_API_ORIGIN='http://127.0.0.1:8000', PREPCREW_WEB_PORT='5173')
    if not live:
        env.update(GEMINI_API_KEY='', ELEVENLABS_API_KEY='', LLM_PROVIDER='fake', VOICE_PROVIDER='fake')
    elif not env.get('GEMINI_API_KEY') or not env.get('GEMINI_MODEL'):
        raise RuntimeError('Live mode requires GEMINI_API_KEY and GEMINI_MODEL in the root .env.')
    return env


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Use configured Gemini (and optional ElevenLabs) keys.')
    args = parser.parse_args()
    env = environment(args.live)
    node = shutil.which('node')
    vite = ROOT / 'frontend/node_modules/vite/bin/vite.js'
    if not node or not vite.exists():
        raise RuntimeError('Install Node.js and run npm ci in frontend first.')
    for port in (8000, 5173):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', port))
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    subprocess.run([sys.executable, '-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head'],
                   cwd=ROOT, env=env, check=True, creationflags=flags)
    children = []
    try:
        for command, cwd in (([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], ROOT),
                             ([node, str(vite), '--host', '127.0.0.1', '--strictPort'], ROOT / 'frontend')):
            children.append(subprocess.Popen(command, cwd=cwd, env=env, creationflags=flags))
        print('PrepCrew: http://127.0.0.1:5173 — create a local account. Ctrl+C stops both servers.', flush=True)
        while all(child.poll() is None for child in children):
            try:
                children[0].wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
        raise RuntimeError('A development server stopped. See its output above.')
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    main()
