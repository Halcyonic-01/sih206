"""Compatibility entry point for shared typechecking and owned Vitest tests."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    source = Path(__file__).resolve().parent
    frontend = source.parents[2]
    if not (frontend / 'node_modules').is_dir():
        print('Run npm ci in frontend/ before checking owned components.', file=sys.stderr)
        return 1
    npm = 'npm.cmd' if os.name == 'nt' else 'npm'
    for command in [[npm, 'run', 'typecheck'],
                    [npm, 'test', '--', 'src/features/saksham/']]:
        result = subprocess.run(command, cwd=frontend, check=False)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
