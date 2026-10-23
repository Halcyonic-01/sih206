"""Install only bundled wheels and create local synthetic demo data, without resetting work."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def verify_package(root):
    manifest = json.loads((root / 'package-manifest.json').read_text(encoding='utf-8'))
    if manifest['format'] != 1 or manifest['python'] != '3.12':
        raise ValueError('Unsupported package manifest')
    for name, expected in manifest['files'].items():
        target = (root / name).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError('Unsafe manifest path')
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Package checksum mismatch: {name}')


def setup():
    if sys.version_info[:2] != (3, 12):
        raise SystemExit('Use Python 3.12 to run this package.')
    verify_package(ROOT)
    python = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not (ROOT / '.venv').exists():
        venv.EnvBuilder(with_pip=False).create(ROOT / '.venv')
    if not python.exists():
        raise SystemExit('Existing .venv is incomplete. Use a fresh extracted package folder.')
    version = subprocess.check_output([str(python), '-c', 'import sys; print("%d.%d" % sys.version_info[:2])'], text=True).strip()
    if version != '3.12':
        raise SystemExit('Existing .venv must use Python 3.12. No environment was replaced.')
    wheels = ROOT / 'wheelhouse'
    pip_wheel = wheels / 'pip-26.2.1-py3-none-any.whl'
    # Bootstrap pip from its wheel; ensurepip and an Internet connection are not required.
    bootstrap = 'import sys,runpy; sys.path.insert(0,sys.argv.pop(1)); runpy.run_module("pip",run_name="__main__")'
    subprocess.run([str(python), '-c', bootstrap, str(pip_wheel), 'install', '--no-index',
                    '--find-links', str(wheels), '--no-cache-dir', '--disable-pip-version-check',
                    'pip==26.2.1', '-r', str(ROOT / 'requirements.txt')], check=True, cwd=ROOT)
    environment = os.environ.copy()
    environment['DJANGO_DEBUG'] = 'true'
    for args in [('migrate', '--noinput'), ('seed_demo', '--generate-password'),
                 ('seed_demo', '--authority-only', '--generate-password'), ('seed_scenarios',), ('check',)]:
        subprocess.run([str(python), 'manage.py', *args], check=True, cwd=ROOT, env=environment)
    print('Offline demo ready. Private credentials: data/demo-credentials.txt and data/authority-credentials.txt.')
    print('Run Start-Demo.ps1, then open http://127.0.0.1:8000/. Demo evaluation date: 2026-10-23.')


if __name__ == '__main__':
    setup()
