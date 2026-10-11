"""Initialize Render's mounted artifact directory and start one API process."""
import os
from pathlib import Path
import sys
import subprocess


def main():
    port = int(os.environ.get('PORT', '10000'))
    if not 1 <= port <= 65535:
        raise ValueError('PORT must be between 1 and 65535')
    if os.environ.get('RENDER_MIGRATE_ON_START') == 'true':
        subprocess.run([sys.executable, '-m', 'alembic', '-c',
                        'backend/alembic.ini', 'upgrade', 'head'], check=True)
    artifacts = Path('/app/.artifacts')
    artifacts.mkdir(exist_ok=True)
    if os.getuid() == 0:
        os.chown(artifacts, 10001, 10001)
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    if not os.access(artifacts, os.W_OK):
        raise PermissionError('Artifact disk is not writable')
    os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'app.main:app',
             '--host', '0.0.0.0', '--port', str(port), '--proxy-headers',
             '--forwarded-allow-ips', '*'])


if __name__ == '__main__':
    main()
