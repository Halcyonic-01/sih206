"""Verify an uncommitted local candidate using the existing fresh-install launcher.

Copies source only to a new ignored directory. Never copies .env, data, planning,
credentials, node_modules, generated output or the current virtual environment.
This complements review_check.py, whose git archive deliberately tests HEAD only.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = {'access', 'ai', 'audit', 'casework', 'config', 'docs', 'fixtures', 'frontend',
               'notifications', 'obligations', 'portal', 'scenarios', 'scripts', 'static', 'templates', 'verification'}
ROOT_FILES = {'manage.py', 'requirements.txt', 'requirements.in', 'run.ps1', 'run.sh', '.env.example', 'README.md'}


def main():
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT).decode().splitlines()
    destination = ROOT / 'data' / 'semifinal-installs' / uuid4().hex[:12]
    destination.mkdir(parents=True)
    hashes = {}
    for name in sorted(set(paths)):
        relative = Path(name)
        if name not in ROOT_FILES and relative.parts[0] not in SOURCE_DIRS:
            continue
        if any(p in {'node_modules', '__pycache__', 'dist', 'data', 'planning'} for p in relative.parts):
            continue
        source = ROOT / relative
        if not source.is_file() or source.is_symlink():
            continue
        if relative.parts[0] == 'docs' and subprocess.run(['git', 'ls-files', '--error-unmatch', name], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    (destination / 'candidate-source-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
    env = {k: v for k, v in os.environ.items() if not k.startswith((
        'DJANGO_', 'DATABASE_', 'EMAIL_', 'GEMINI_', 'AI_', 'OCR_', 'AUDIT_', 'PORTAL_', 'NOTIFY_'))}
    env.update(DJANGO_SETTINGS_MODULE='config.settings', DATABASE_BACKEND='sqlite', AI_ENABLED='false', OCR_ENABLED='false',
               EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend', NOTIFY_SEND_ON_COMMIT='false')
    print(f'Source-only fresh candidate: {destination}', flush=True)
    subprocess.run([sys.executable, str(destination / 'scripts/run_portal.py'), '--smoke', '--port', '8016'],
                   cwd=destination, env=env, check=True)
    print('Fresh candidate install and smoke passed; source hashes retained beside it.', flush=True)


if __name__ == '__main__':
    main()
