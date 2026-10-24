"""Supabase/PostgreSQL connection settings; no credentials are logged."""
import os
import re
from urllib.parse import parse_qs, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured


def private_schema(value):
    if (not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', value) or value.startswith('pg_') or value in
        {'public', 'auth', 'storage', 'extensions', 'realtime', 'graphql', 'graphql_public', 'information_schema', 'vault', 'supabase_functions'}):
        raise ImproperlyConfigured('DATABASE_SCHEMA must name a private application schema, for example portal_app.')
    return value


def database_config(base_dir, environ=None, *, testing=False):
    env = os.environ if environ is None else environ
    backend = env.get('DATABASE_BACKEND', 'auto').strip().lower()
    if backend not in ('auto', 'sqlite', 'postgresql'):
        raise ImproperlyConfigured('DATABASE_BACKEND must be auto, sqlite or postgresql.')
    url = env.get('DATABASE_URL', '').strip()
    # Existing test commands stay local even when the application uses Supabase.
    if testing or backend == 'sqlite' or (backend == 'auto' and not url):
        return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': base_dir / 'data/portal.sqlite3',
                'OPTIONS': {'timeout': 20}}
    if not url:
        raise ImproperlyConfigured('Set DATABASE_URL in the ignored .env file or process environment.')
    try:
        parsed = urlsplit(url)
        port = parsed.port or 5432
        name = unquote(parsed.path.lstrip('/'))
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
        if (parsed.scheme not in ('postgres', 'postgresql') or not parsed.hostname or not parsed.username
                or not parsed.password or not name or '/' in name or parsed.fragment
                or not 1 <= port <= 65535 or set(query) - {'sslmode', 'sslrootcert'}
                or any(len(values) != 1 for values in query.values())):
            raise ValueError()
    except (ValueError, UnicodeError):
        raise ImproperlyConfigured('DATABASE_URL must be a valid PostgreSQL URI with host, database, user and password. Percent-encode password punctuation.') from None
    if port == 6543:
        raise ImproperlyConfigured('Use the Supabase Session pooler on port 5432 or a direct connection; transaction pooling is not supported here.')
    mode = query.get('sslmode', [env.get('DATABASE_SSLMODE', 'require')])[0]
    if mode not in ('require', 'verify-ca', 'verify-full'):
        raise ImproperlyConfigured('PostgreSQL requires TLS: DATABASE_SSLMODE must be require, verify-ca or verify-full.')
    schema = private_schema(env.get('DATABASE_SCHEMA', 'portal_app'))
    options = {'sslmode': mode, 'connect_timeout': 10, 'options': f'-c search_path={schema}',
               'prepare_threshold': None}
    root_cert = query.get('sslrootcert', [env.get('DATABASE_SSL_ROOT_CERT', '')])[0]
    if root_cert:
        options['sslrootcert'] = root_cert
    return {'ENGINE': 'django.db.backends.postgresql', 'NAME': name,
        'USER': unquote(parsed.username), 'PASSWORD': unquote(parsed.password),
        'HOST': parsed.hostname, 'PORT': port, 'CONN_MAX_AGE': 0, 'CONN_HEALTH_CHECKS': True,
        'DISABLE_SERVER_SIDE_CURSORS': True, 'OPTIONS': options}
