"""Compile/test isolated components using an ignored local toolchain, no shell."""
import json
from pathlib import Path
import subprocess
import sys


def main():
    source = Path(__file__).resolve().parent
    root = source.parents[3]
    runtime = root / 'data/saksham-ui-tools'
    compiler = runtime / 'node_modules/typescript/bin/tsc'
    if not compiler.exists():
        print('Install the local test toolchain using this feature folder README.', file=sys.stderr)
        return 1
    config = {'compilerOptions': {'target': 'ES2021', 'module': 'Node16', 'moduleResolution': 'Node16',
        'jsx': 'react', 'strict': True, 'esModuleInterop': True, 'skipLibCheck': True,
        'lib': ['ES2021', 'DOM'], 'outDir': (runtime / 'build').as_posix(),
        'rootDir': source.as_posix(), 'typeRoots': [(runtime / 'node_modules/@types').as_posix()],
        'paths': {'react': [(runtime / 'node_modules/@types/react/index.d.ts').as_posix()]}},
        'include': [(source / '*.ts').as_posix(), (source / '*.tsx').as_posix()]}
    target = runtime / 'tsconfig.json'
    target.write_text(json.dumps(config), encoding='utf-8')
    for command in [['node', str(compiler), '-p', str(target)],
                    ['node', str(source / 'tests.cjs'), str(runtime)]]:
        result = subprocess.run(command, cwd=root, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
