"""Tiny .env reader (no dependency). Real environment variables always win over the file."""
import os
from pathlib import Path


def parse_env_text(text):
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip().removeprefix('export ').strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        elif ' #' in value:
            value = value.split(' #', 1)[0].rstrip()
        if key.isidentifier():
            values[key] = value
    return values


def load_env_file(path):
    path = Path(path)
    if not path.is_file():
        return {}
    values = parse_env_text(path.read_text(encoding='utf-8'))
    for key, value in values.items():
        os.environ.setdefault(key, value)
    return values
