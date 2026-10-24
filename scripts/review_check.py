"""Pre-tag verification for the review build (K8). Never tags, pushes or changes the repository.

    python scripts/review_check.py [--skip-fresh-install] [--allow-dirty]

Runs the Django and React checks on the working tree, then installs the *committed* files into an empty temporary
folder and starts the production-mode build there (sign-in, notifications, audit chain). Standard library only.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
PYTHON = str(VENV_PYTHON if VENV_PYTHON.exists() else sys.executable)
NPM = shutil.which('npm')
PRODUCTION_ENV = {
    'DJANGO_DEBUG': 'false', 'DJANGO_SECRET_KEY': 'review-check-not-a-real-secret-0123456789abcdefghijklmnop',
    'DJANGO_ALLOWED_HOSTS': 'example.org', 'DJANGO_SECURE_COOKIES': 'true', 'DJANGO_SECURE_SSL_REDIRECT': 'true',
    'DJANGO_HSTS_SECONDS': '31536000',
}
results = []


def step(name, command, cwd=ROOT, env=None):
    started = time.time()
    print(f'\n== {name}', flush=True)
    completed = subprocess.run([str(part) for part in command], cwd=cwd, env={**os.environ, **(env or {})})
    ok = completed.returncode == 0
    results.append((name, ok, time.time() - started))
    return ok


def fresh_install():
    with tempfile.TemporaryDirectory(prefix='fdr-review-') as folder:
        archive = Path(folder) / 'head.tar'
        subprocess.run(['git', 'archive', '--format=tar', '-o', str(archive), 'HEAD'], cwd=ROOT, check=True)
        target = Path(folder) / 'clean'
        target.mkdir()
        with tarfile.open(archive) as tar:
            tar.extractall(target, filter='data')
        return step('Fresh install of the committed files, production mode (run_portal.py --smoke --prod)',
                    [sys.executable, 'scripts/run_portal.py', '--smoke', '--prod', '--port', '8016'], cwd=target)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--skip-fresh-install', action='store_true')
    parser.add_argument('--allow-dirty', action='store_true', help='check even with uncommitted changes')
    args = parser.parse_args()

    status = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if status and not args.allow_dirty:
        print('Uncommitted changes: the fresh-install step tests the committed files only.\n'
              'Commit first, or pass --allow-dirty.\n' + status)
        return 2
    step('Django system check', [PYTHON, 'manage.py', 'check'])
    step('Migrations match the models', [PYTHON, 'manage.py', 'makemigrations', '--check', '--dry-run'])
    step('Production-profile deploy check', [PYTHON, 'manage.py', 'check', '--deploy', '--fail-level', 'WARNING'],
         env=PRODUCTION_ENV)
    step('Django tests (all apps)', [PYTHON, 'manage.py', 'test', '--noinput'])
    if NPM:
        step('React type-check', [NPM, 'run', 'typecheck'], cwd=ROOT / 'frontend')
        step('React tests', [NPM, 'test'], cwd=ROOT / 'frontend')
        step('React production build', [NPM, 'run', 'build'], cwd=ROOT / 'frontend')
    else:
        results.append(('React checks (npm not found)', False, 0))
    if not args.skip_fresh_install:
        fresh_install()

    print('\n== Summary')
    for name, ok, seconds in results:
        print(f'  {"PASS" if ok else "FAIL"}  {name} ({seconds:.0f}s)')
    if all(ok for _, ok, _ in results):
        print('\nAll checks passed. When every pull request is merged and CI is green, tag the build:\n'
              '  git tag -a review-1 -m "Review build 25 Oct 2026" && git push origin review-1')
        return 0
    print('\nFix the failures above before tagging.')
    return 1


if __name__ == '__main__':
    sys.exit(main())
