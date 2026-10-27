"""Prepare the existing app's disposable rehearsal profile, without resetting data."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    destination = ROOT / 'data' / 'semifinal'
    (destination / 'data').mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'fixtures', destination / 'fixtures', dirs_exist_ok=True)
    commands = [(['migrate', '--noinput'], None),
        (['seed_demo', '--generate-password'], 'demo-credentials.txt'),
        (['seed_demo', '--authority-only', '--generate-password'], 'authority-credentials.txt'),
        (['seed_staff', '--generate-password'], 'staff-credentials.txt'),
        (['seed_scenarios'], '.semifinal-scenarios-seeded'),
        (['seed_review'], '.semifinal-review-seeded'),
        (['seed_yash_examples'], '.semifinal-records-seeded'),
        (['seed_semifinal_release'], None)]
    for args, marker in commands:
        target = destination / 'data' / marker if marker else None
        if target and target.exists():
            continue
        subprocess.run([sys.executable, str(ROOT / 'manage.py'), *args,
                        '--settings=config.rehearsal_settings'], cwd=ROOT, check=True)
        if target and not target.exists():
            target.touch()
    print('Disposable setup ready. Private credentials: data/semifinal/data/*-credentials.txt')
    print('Start: .venv\\Scripts\\python.exe manage.py runserver 127.0.0.1:8011 --settings=config.rehearsal_settings --noreload')


if __name__ == '__main__':
    main()
