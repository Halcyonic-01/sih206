"""Build a source + pinned wheel archive. Never copies live data or credentials."""
import argparse
from datetime import datetime, timezone
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import shutil
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ('config', 'portal', 'obligations', 'verification', 'ai', 'templates', 'static', 'fixtures', 'scripts', 'docs', 'evaluation')
FRONTEND_FOLDERS = ('frontend/src', 'frontend/tests', 'frontend/dist/records')
FRONTEND_FILES = ('package.json', 'package-lock.json', 'index.html', 'tsconfig.json',
                  'tsconfig.app.json', 'tsconfig.node.json', 'vite.config.ts', 'playwright.config.ts')
FILES = ('manage.py', 'requirements.txt', 'requirements.in', 'README.md', '.env.example',
         '.gitignore', 'Setup-Offline.ps1', 'Start-Demo.ps1', 'Verify-Demo.ps1')
PIP_VERSION = '26.2.1'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_wheels(wheel_dir):
    required = dict(line.strip().lower().split('==') for line in
                    (ROOT / 'requirements.txt').read_text().splitlines() if line.strip())
    required['pip'] = PIP_VERSION
    found = {}
    wheels = sorted(wheel_dir.glob('*.whl'))
    for wheel in wheels:
        with ZipFile(wheel) as archive:
            metadata, = [name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
            fields = BytesParser().parsebytes(archive.read(metadata))
            name = fields['Name'].lower()
            if name in found:
                raise ValueError(f'Duplicate wheel: {name}')
            found[name] = fields['Version']
    if found != required:
        raise ValueError(f'Wheel versions must exactly match {required}; found {found}')
    return wheels


def build(wheel_dir):
    if (ROOT / 'frontend').exists() and not (ROOT / 'frontend/dist/records/index.html').is_file():
        raise ValueError('Build the frontend first: cd frontend and run npm ci then npm run build')
    wheels = check_wheels(wheel_dir)
    destination = ROOT / 'dist' / ('fdr-demo-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    destination.mkdir(parents=True, exist_ok=False)
    for folder in (*FOLDERS, *FRONTEND_FOLDERS):
        for source in (ROOT / folder).rglob('*'):
            if (not source.is_file() or source.is_symlink()
                    or any(part in ('__pycache__', 'node_modules', '.env') for part in source.relative_to(ROOT).parts)
                    or source.suffix in ('.pyc', '.pyo')
                    or not source.resolve().is_relative_to(ROOT.resolve())):
                continue
            target = destination / source.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    for name in FILES:
        shutil.copyfile(ROOT / name, destination / name)
    for name in FRONTEND_FILES:
        source = ROOT / 'frontend' / name
        if source.is_file() and not source.is_symlink():
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
