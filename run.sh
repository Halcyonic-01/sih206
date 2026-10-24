#!/usr/bin/env bash
# Build the React app and start the portal on one port. Usage: ./run.sh [--port 8010] [--dev] [--prod] [--smoke]
set -euo pipefail
cd "$(dirname "$0")"
for candidate in python3.12 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && \
     "$candidate" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)' 2>/dev/null; then
    exec "$candidate" scripts/run_portal.py "$@"
  fi
done
# An existing .venv already pins Python 3.12, so any interpreter can launch the script.
if [ -x .venv/bin/python ]; then exec .venv/bin/python scripts/run_portal.py "$@"; fi
echo "Python 3.12 is required (python3.12 not found). Install it from python.org or your package manager." >&2
exit 1
