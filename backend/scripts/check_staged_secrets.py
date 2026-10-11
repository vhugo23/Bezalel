"""Fail before publication if staged files contain configured secrets/artifacts."""
from pathlib import Path
import re
import subprocess
from dotenv import dotenv_values


def main():
    paths = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], text=True).splitlines()
    secrets = {}
    for env_path in (Path('.env'), Path('backend/.env'), Path('frontend/.env')):
        if env_path.exists():
            for key, value in dotenv_values(env_path).items():
                if value and len(value) >= 12 and re.search(r'KEY|TOKEN|SECRET|PASSWORD|DATABASE_URL|DB_URL', key, re.I):
                    secrets[key] = value.encode()
    issues = []
    for path in paths:
        name = Path(path).name
        if (name.startswith('.env') and name != '.env.example') or any(
            part in ('node_modules', '.artifacts', '__pycache__', 'dist', 'test-results') for part in Path(path).parts
        ):
            issues.append((path, 'excluded local file'))
        data = subprocess.check_output(['git', 'show', ':' + path])
        for key, value in secrets.items():
            if value in data:
                issues.append((path, 'contains configured secret ' + key))
        for label, pattern in (
            ('private key', rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
            ('Google API key', rb'AIza[0-9A-Za-z_-]{35}'),
            ('GitHub token', rb'gh[pousr]_[A-Za-z0-9]{30,}'),
        ):
            if re.search(pattern, data):
                issues.append((path, label))
    for path, label in issues:
        print(f'BLOCKED: {path}: {label}')
    if issues:
        return 1
    print(f'Checked {len(paths)} staged files; no configured secrets or local artifacts detected.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
