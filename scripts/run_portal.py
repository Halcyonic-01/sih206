"""One command to build the React app and start Django on a single port (K3).

    python scripts/run_portal.py                 # first run installs everything, then serves http://127.0.0.1:8010/
    python scripts/run_portal.py --dev           # Django with reload + Vite dev server on :5173
    python scripts/run_portal.py --prod          # production-like settings: DEBUG off, collected static files
    python scripts/run_portal.py --smoke         # set up, start, check the key URLs, stop (used by CI)

Standard library only; run it with any Python 3.12. It re-uses `.venv`, skips work that is already
done (hash markers) and never resets existing data. Local synthetic data only.
"""
import argparse
import hashlib
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend'
VENV = ROOT / '.venv'
VENV_PYTHON = VENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
CREDENTIALS = ROOT / 'data' / 'demo-credentials.txt'


def say(message):
    print(f'[run] {message}', flush=True)


def digest(*paths):
    sha = hashlib.sha256()
    for path in paths:
        sha.update(Path(path).read_bytes())
    return sha.hexdigest()


def run(command, cwd=ROOT, env=None, check=True):
    return subprocess.run([str(part) for part in command], cwd=cwd, env=env, check=check)


def ensure_python_env():
    if not VENV_PYTHON.exists():
        if sys.version_info[:2] != (3, 12):
            raise SystemExit('Use Python 3.12 to create the environment (found %d.%d).' % sys.version_info[:2])
        say('Creating .venv')
        venv.EnvBuilder(with_pip=True).create(VENV)
    version = subprocess.check_output([str(VENV_PYTHON), '-c', 'import sys; print("%d.%d" % sys.version_info[:2])'],
                                      text=True).strip()
    if version != '3.12':
        raise SystemExit(f'.venv uses Python {version}; delete it and rerun with Python 3.12.')
    marker = VENV / '.requirements.sha256'
    wanted = digest(ROOT / 'requirements.txt')
    if not marker.exists() or marker.read_text().strip() != wanted:
        say('Installing Python requirements')
        run([VENV_PYTHON, '-m', 'pip', 'install', '--disable-pip-version-check', '-q', '-r', ROOT / 'requirements.txt'])
        marker.write_text(wanted)


def find_npm():
    return shutil.which('npm')


def build_frontend(skip_build):
    dist_index = FRONTEND / 'dist' / 'index.html'
    npm = find_npm()
    if skip_build:
        say('Skipping the React build (--skip-build)')
        return
    if not npm:
        if dist_index.exists():
            say('npm not found; using the existing frontend/dist build')
            return
        raise SystemExit('Node.js 22+ (npm) is required to build the React app. Install it from nodejs.org.')
    marker = FRONTEND / 'node_modules' / '.lock.sha256'
    wanted = digest(FRONTEND / 'package-lock.json')
    if not marker.exists() or marker.read_text().strip() != wanted:
        say('Installing frontend packages (npm ci)')
        run([npm, 'ci', '--no-audit', '--no-fund'], cwd=FRONTEND)
        marker.write_text(wanted)
    say('Building the React app')
    run([npm, 'run', 'build'], cwd=FRONTEND)


def prod_secret():
    """Stable random key for production-like local runs, kept in git-ignored data/."""
    path = ROOT / 'data' / '.secret_key'
    path.parent.mkdir(exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_urlsafe(50))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path.read_text().strip()


def django_env(prod):
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = '1'
    if prod:
        env['DJANGO_DEBUG'] = 'false'
        env.setdefault('DJANGO_SECRET_KEY', prod_secret())
    return env


def manage(*args, env, check=True):
    return run([VENV_PYTHON, 'manage.py', *args], env=env, check=check)


def prepare_database(env, force_seed, prod):
    manage('migrate', '--noinput', env=env)
    first_run = not CREDENTIALS.exists()
    if first_run or force_seed:
        say('Creating synthetic demo accounts and scenario records')
        seed_env = {**env, 'DJANGO_DEBUG': 'true'}  # generated credentials are allowed in local DEBUG only
        for args in (('seed_demo', '--generate-password'), ('seed_demo', '--authority-only', '--generate-password'),
                     ('seed_scenarios',)):
            result = manage(*args, env=seed_env, check=False)
            if result.returncode:
                say(f'{" ".join(args)} did not run (already seeded?); continuing')
    if prod:
        manage('collectstatic', '--noinput', '-v', '0', env=env)


def wait_for(url, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                return response.status, response.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as error:
            return error.code, ''
        except OSError:
            time.sleep(0.5)
    raise SystemExit(f'Timed out waiting for {url}')


def squash(text):
    return ''.join(text.split()).lower()


def smoke(base, prod=False):
    checks = [('/api/health/', 200, '"status":"ok"'), ('/', 200, 'id="root"'), ('/login', 200, 'id="root"'),
              # API docs need a signed-in user unless API_DOCS_PUBLIC=true (the default only in DEBUG).
              ('/api/docs/', 401 if prod else 200, '' if prod else 'swagger'), ('/legacy/accounts/login/', 200, 'csrfmiddlewaretoken'),
              ('/api/auth/me/', 401, '')]
    failed = []
    for path, status, needle in checks:
        got, body = wait_for(base + path)
        ok = got == status and squash(needle) in squash(body)
        say(f'{"ok  " if ok else "FAIL"} {path} -> {got}')
        if not ok:
            failed.append(path)
    if failed:
        raise SystemExit('Smoke check failed: ' + ', '.join(failed))
    say('Smoke check passed')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8010)
    parser.add_argument('--dev', action='store_true', help='Django autoreload + Vite dev server (hot reload)')
    parser.add_argument('--prod', action='store_true', help='DEBUG off, collectstatic, production-like settings')
    parser.add_argument('--skip-build', action='store_true', help='reuse frontend/dist')
    parser.add_argument('--seed', action='store_true', help='(re)run the demo seed commands')
    parser.add_argument('--smoke', action='store_true', help='start, check key URLs, stop (CI)')
    args = parser.parse_args()
    if args.dev and args.prod:
        parser.error('--dev and --prod cannot be combined')

    ensure_python_env()
    if not args.dev:
        build_frontend(args.skip_build)
    elif not find_npm():
        raise SystemExit('Node.js 22+ (npm) is required for --dev.')
    env = django_env(args.prod)
    manage('check', env=env)
    prepare_database(env, args.seed, args.prod)

    address = f'{args.host}:{args.port}'
    command = [VENV_PYTHON, 'manage.py', 'runserver', address] + ([] if args.dev else ['--noreload'])
    say(f'Starting Django at http://{address}/')
    server = subprocess.Popen([str(part) for part in command], cwd=ROOT, env=env)
    vite = None
    try:
        if args.smoke:
            smoke(f'http://{address}', args.prod)
            return
        if args.dev:
            npm = find_npm()
            if not (FRONTEND / 'node_modules').exists():
                run([npm, 'ci', '--no-audit', '--no-fund'], cwd=FRONTEND)
            say('Starting Vite at http://localhost:5173/ (use this URL while developing)')
            vite = subprocess.Popen([npm, 'run', 'dev'], cwd=FRONTEND,
                                    env={**env, 'DJANGO_URL': f'http://{address}'})
        say(f'Ready: open http://{address}/  (sign-in accounts: {CREDENTIALS.relative_to(ROOT)} , '
            'data/authority-credentials.txt). Ctrl+C stops.')
        while server.poll() is None and (vite is None or vite.poll() is None):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in (vite, server):
            if process and process.poll() is None:
                process.terminate()
        for process in (vite, server):
            if process:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == '__main__':
    main()
