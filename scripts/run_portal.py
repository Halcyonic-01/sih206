"""One command to build the React app and start Django on a single port (K3).

    python scripts/run_portal.py                 # first run installs everything, then serves http://127.0.0.1:8010/
    python scripts/run_portal.py --dev           # Django with reload + Vite dev server on :5173
    python scripts/run_portal.py --prod          # production-like settings: DEBUG off, collected static files
    python scripts/run_portal.py --smoke         # set up, start, check the key URLs, stop (used by CI)

Everything the portal needs runs from this one command: .env is created on the first run, the database is
migrated and seeded, the daily rules and e-mail retries run in the background (--no-scheduler to turn off) and,
when .env points EMAIL_HOST at localhost:1025, the Mailpit mail catcher is started if it is installed
(--no-mailpit to turn off), with its inbox at http://127.0.0.1:8025/.

Standard library only; run it with any Python 3.12. It re-uses `.venv`, skips work that is already
done (hash markers) and never resets existing data. Local synthetic data only.
"""
import argparse
import hashlib
import os
import secrets
import shutil
import socket
import subprocess
import sys
import time
import json
from datetime import datetime, timezone
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend'
VENV = ROOT / '.venv'
VENV_PYTHON = VENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
CREDENTIALS = ROOT / 'data' / 'demo-credentials.txt'
STAFF_CREDENTIALS = ROOT / 'data' / 'staff-credentials.txt'
REVIEW_MANIFEST = ROOT / 'data' / 'seed-review-v2.json'
ENV_FILE = ROOT / '.env'
ENV_EXAMPLE = ROOT / '.env.example'
DATABASE = ROOT / 'data' / 'portal.sqlite3'
MAILPIT_SMTP = 1025
MAILPIT_UI = 8025
SEND_EVERY_SECONDS = 300


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
    manage('seal_audit_chain', env=env)  # seals audit events written before the hash chain existed
    seed_env = {**env, 'DJANGO_DEBUG': 'true'}  # generated credentials are allowed in local DEBUG only
    steps = []
    if force_seed or not CREDENTIALS.exists():
        steps += [('seed_demo', '--generate-password'), ('seed_demo', '--authority-only', '--generate-password'),
                  ('seed_scenarios',)]
    if force_seed or not STAFF_CREDENTIALS.exists():
        steps.append(('seed_staff', '--generate-password'))
    if force_seed or not REVIEW_MANIFEST.exists():
        steps.append(('seed_review',) + (('--force',) if force_seed else ()))
    if steps:
        say('Creating synthetic demo accounts and scenario records')
    for args in steps:
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


def read_password(path, username):
    for line in path.read_text(encoding='utf-8').splitlines():
        name, _, value = line.partition(': ')
        if name == username:
            return value.strip()
    return None


class Session:
    """Minimal cookie + CSRF aware API client for the smoke check."""

    def __init__(self, base):
        self.base = base
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def csrf(self):
        self.opener.open(self.base + '/api/auth/csrf/', timeout=10).read()
        return next(cookie.value for cookie in self.jar if cookie.name == 'csrftoken')

    def call(self, path, body=None):
        headers = {'Accept': 'application/json'}
        data = None
        if body is not None:
            headers.update({'Content-Type': 'application/json', 'X-CSRFToken': self.csrf()})
            data = json.dumps(body).encode()
        try:
            with self.opener.open(urllib.request.Request(self.base + path, data=data, headers=headers), timeout=15) as response:
                return response.status, json.loads(response.read() or b'null')
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b'null')


def smoke_accounts(base, failed):
    """Sign in with the generated demo passwords (never printed) and exercise the platform end to end."""
    for username, role, path in (('officer', 'officer', CREDENTIALS), ('auditor', 'auditor', STAFF_CREDENTIALS)):
        password = read_password(path, username) if path.exists() else None
        if not password:
            say(f'skip {username}: no generated password found')
            continue
        session = Session(base)
        status, body = session.call('/api/auth/login/', {'username': username, 'password': password})
        ok = status == 200 and body and body.get('role') == role
        say(f'{"ok  " if ok else "FAIL"} sign in as {username} -> {status}')
        if not ok:
            failed.append(f'login {username}')
            continue
        if role == 'officer':
            status, body = session.call('/api/notifications/unread-count/')
            ok = status == 200
            say(f'{"ok  " if ok else "FAIL"} notifications API -> {status}')
        else:
            status, body = session.call('/api/audit/chain/verify/')
            ok = status == 200 and body.get('status') == 'ok'
            say(f'{"ok  " if ok else "FAIL"} audit chain -> {status} {body.get("status") if body else ""}')
            status, body = session.call('/api/audit/access-log/')
            ok2 = status == 200 and body.get('count', 0) > 0
            say(f'{"ok  " if ok2 else "FAIL"} access log has rows -> {status}')
            ok = ok and ok2
        if not ok:
            failed.append(f'{role} checks')


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
    smoke_accounts(base, failed)
    if failed:
        raise SystemExit('Smoke check failed: ' + ', '.join(failed))
    say('Smoke check passed')


def ensure_env_file():
    """Create .env from .env.example with fresh random keys, but only on a first run (no .env and no database yet).

    An existing database was sealed with its own audit key, so a new key must never be generated for it.
    """
    if ENV_FILE.exists() or not ENV_EXAMPLE.exists():
        return
    if DATABASE.exists():
        say('No .env found; using built-in local defaults (copy .env.example to .env to configure e-mail and HTTPS)')
        return
    text = ENV_EXAMPLE.read_text(encoding='utf-8')
    lines = []
    for line in text.splitlines():
        if line.startswith('DJANGO_SECRET_KEY='):
            line = 'DJANGO_SECRET_KEY=' + secrets.token_urlsafe(50)
        elif line.startswith('AUDIT_CHAIN_KEY='):
            line = 'AUDIT_CHAIN_KEY=' + secrets.token_hex(32)
        lines.append(line)
    ENV_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    try:
        ENV_FILE.chmod(0o600)
    except OSError:
        pass
    say('Created .env from .env.example with new random keys (git-ignored; see the comments inside for what to change)')


def dotenv_settings():
    """The .env file overlaid by real environment variables, the same precedence settings.py uses."""
    sys.path.insert(0, str(ROOT))
    try:
        from config.envfile import parse_env_text
    finally:
        sys.path.pop(0)
    values = parse_env_text(ENV_FILE.read_text(encoding='utf-8')) if ENV_FILE.is_file() else {}
    values.update({key: value for key, value in os.environ.items() if key in values or key.startswith('EMAIL_')})
    return values


def port_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def start_mailpit(settings):
    """Start the local mail catcher when .env sends mail to localhost:1025. Returns the process or None."""
    host, port = settings.get('EMAIL_HOST', ''), settings.get('EMAIL_PORT', '')
    if host not in ('localhost', '127.0.0.1') or port != str(MAILPIT_SMTP):
        return None
    if port_open('127.0.0.1', MAILPIT_SMTP):
        say(f'A mail catcher is already running on port {MAILPIT_SMTP}; inbox at http://127.0.0.1:{MAILPIT_UI}/')
        return None
    binary = shutil.which('mailpit')
    if not binary:
        say('EMAIL_HOST points at localhost:1025 but Mailpit is not installed, so e-mails are kept and retried later. '
            'Install it (macOS: brew install mailpit; others: https://mailpit.axllent.org/docs/install/) '
            'and run this script again.')
        return None
    say(f'Starting Mailpit: inbox at http://127.0.0.1:{MAILPIT_UI}/')
    return subprocess.Popen([binary, '--smtp', f'127.0.0.1:{MAILPIT_SMTP}', '--listen', f'127.0.0.1:{MAILPIT_UI}'],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def background_command(name, env):
    """Run a short management command for the scheduler; print only its last line (or the failure)."""
    result = subprocess.run([str(VENV_PYTHON), 'manage.py', name], cwd=ROOT, env=env, text=True,
                            capture_output=True, check=False)
    tail = (result.stdout.strip().splitlines() or [''])[-1]
    if result.returncode:
        say(f'scheduler: {name} failed ({(result.stderr.strip().splitlines() or ["no output"])[-1]})')
    elif tail:
        say(f'scheduler: {name}: {tail}')
    return result.returncode


def scheduler_tick(env, state):
    """Local stand-in for the Docker scheduler: e-mail retries every 5 minutes, due rules once per day."""
    now = time.time()
    if now >= state['next_send']:
        state['next_send'] = now + SEND_EVERY_SECONDS
        background_command('send_notifications', env)
    stamp = ROOT / 'data' / f'.rules-ran-{datetime.now(timezone.utc):%Y-%m-%d}'
    if not stamp.exists() and now >= state['next_rules']:
        state['next_rules'] = now + SEND_EVERY_SECONDS  # a failed run is retried later, not in a tight loop
        if background_command('run_due_rules', env) == 0:
            stamp.parent.mkdir(exist_ok=True)
            stamp.touch()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8010)
    parser.add_argument('--dev', action='store_true', help='Django autoreload + Vite dev server (hot reload)')
    parser.add_argument('--prod', action='store_true', help='DEBUG off, collectstatic, production-like settings')
    parser.add_argument('--skip-build', action='store_true', help='reuse frontend/dist')
    parser.add_argument('--seed', action='store_true', help='(re)run the demo seed commands')
    parser.add_argument('--smoke', action='store_true', help='start, check key URLs, stop (CI)')
    parser.add_argument('--no-scheduler', action='store_true', help='do not run send_notifications / run_due_rules')
    parser.add_argument('--no-mailpit', action='store_true', help='do not start the Mailpit mail catcher')
    args = parser.parse_args()
    if args.dev and args.prod:
        parser.error('--dev and --prod cannot be combined')

    if not args.smoke:
        ensure_env_file()
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
    mailpit = None
    background = not (args.smoke or args.no_scheduler)
    state = {'next_send': time.time() + 10, 'next_rules': time.time() + 20}
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
        if not args.no_mailpit:
            mailpit = start_mailpit(dotenv_settings())
        say(f'Ready: open http://{address}/  (sign-in accounts: {CREDENTIALS.relative_to(ROOT)} , '
            'data/authority-credentials.txt , data/staff-credentials.txt). Ctrl+C stops.')
        if background:
            say('Scheduler on: e-mail retries every 5 minutes, due rules once a day (--no-scheduler to turn off)')
        while server.poll() is None and (vite is None or vite.poll() is None):
            if background:
                scheduler_tick(env, state)
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in (vite, server, mailpit):
            if process and process.poll() is None:
                process.terminate()
        for process in (vite, server, mailpit):
            if process:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == '__main__':
    main()
