"""Build a source + pinned wheel archive. Never copies live data or credentials."""
import argparse
from datetime import datetime, timezone
from email.parser import BytesParser
import hashlib
import json
import re
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('config', 'portal', 'obligations', 'casework', 'verification', 'ai', 'access', 'notifications', 'audit', 'scenarios', 'docker',
           'templates', 'static', 'fixtures', 'scripts', 'docs', 'evaluation')
FILES = ('manage.py', 'requirements.txt', 'requirements.in', 'README.md', '.env.example',
         '.gitignore', 'Setup-Offline.ps1', 'Start-Demo.ps1', 'Verify-Demo.ps1', 'run.ps1', 'run.sh',
         'Dockerfile', 'docker-compose.yml', '.dockerignore')
PIP_VERSION = '26.2.1'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_wheels(wheel_dir):
    canonical = lambda name: re.sub(r'[-_.]+', '-', name).lower()
    required = {canonical(name): version for name, version in (line.strip().split('==') for line in
                    (ROOT / 'requirements.txt').read_text().splitlines() if line.strip())}
    required['pip'] = PIP_VERSION
    found = {}
    wheels = sorted(wheel_dir.glob('*.whl'))
    for wheel in wheels:
        with ZipFile(wheel) as archive:
            metadata, = [name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
            fields = BytesParser().parsebytes(archive.read(metadata))
            name = canonical(fields['Name'])
            if name in found:
                raise ValueError(f'Duplicate wheel: {name}')
            found[name] = fields['Version']
    if found != required:
        raise ValueError(f'Wheel versions must exactly match {required}; found {found}')
    return wheels


def build(wheel_dir):
    if (ROOT / 'frontend').exists() and not (ROOT / 'frontend/dist/index.html').is_file():
        raise ValueError('Build the frontend first: cd frontend and run npm ci then npm run build')
    wheels = check_wheels(wheel_dir)
    destination = ROOT / 'dist' / ('fdr-demo-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    destination.mkdir(parents=True, exist_ok=False)
    # The React build is generated, so it is copied when present (cd frontend && npm ci && npm run build).
    frontend_dist = ROOT / 'frontend' / 'dist'
    if not (frontend_dist / 'index.html').exists():
        print('WARNING: frontend/dist is missing; the package will show build instructions instead of the React app.')
    for folder in (*FOLDERS, 'frontend/src', 'frontend/tests'):
        for source in (ROOT / folder).rglob('*'):
            if (not source.is_file() or source.is_symlink() or '__pycache__' in source.parts or 'node_modules' in source.parts or '.env' in source.parts or source.suffix in ('.pyc', '.pyo')):
                continue
            target = destination / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    for source in frontend_dist.rglob('*') if frontend_dist.is_dir() else []:
        if source.is_file():
            target = destination / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    for name in FILES:
        shutil.copyfile(ROOT / name, destination / name)
    for name in ('package.json', 'package-lock.json', 'index.html', 'tsconfig.json', 'vite.config.ts', 'playwright.config.ts'):
        source = ROOT / 'frontend' / name
        if source.is_file():
            (destination / 'frontend').mkdir(exist_ok=True)
            shutil.copyfile(source, destination / 'frontend' / name)
    (destination / 'wheelhouse').mkdir()
    for wheel in wheels:
        shutil.copyfile(wheel, destination / 'wheelhouse' / wheel.name)
    hashes = {file.relative_to(destination).as_posix(): sha256(file)
              for file in sorted(destination.rglob('*')) if file.is_file()}
    manifest = {'format': 1, 'python': '3.12', 'files': hashes,
                'note': 'Synthetic demo; Python 3.12 must already be installed. No live data included.'}
    (destination / 'package-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    zip_path = destination.with_suffix('.zip')
    with ZipFile(zip_path, 'x', ZIP_DEFLATED) as archive:
        for name in [*hashes, 'package-manifest.json']:
            archive.write(destination / name, destination.name + '/' + name)
    zip_path.with_suffix('.zip.sha256').write_text(sha256(zip_path) + '  ' + zip_path.name + '\n', encoding='ascii')
    print(destination)
    print(zip_path)
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wheel-dir', type=Path, default=ROOT / '.offline-wheels')
    build(parser.parse_args().wheel_dir)
