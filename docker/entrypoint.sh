#!/bin/sh
# Container start-up: secret key, migrations, audit-chain seal, first-run demo data, then the web server.
set -eu
cd /app

# A stable random key kept in the data volume unless one is supplied.
if [ -z "${DJANGO_SECRET_KEY:-}" ]; then
  if [ ! -s data/.secret_key ]; then
    python -c "import secrets; print(secrets.token_urlsafe(50))" > data/.secret_key
    chmod 600 data/.secret_key
  fi
  DJANGO_SECRET_KEY="$(cat data/.secret_key)"
  export DJANGO_SECRET_KEY
fi

python manage.py migrate --noinput
python manage.py seal_audit_chain

# Synthetic demo accounts on the first start only. Generated passwords are written to the data volume
# (never printed); read them with: docker compose exec web cat data/demo-credentials.txt
if [ "${SEED_DEMO:-true}" = "true" ] && [ ! -f data/demo-credentials.txt ]; then
  echo "First start: creating synthetic demo accounts and scenario records"
  DJANGO_DEBUG=true python manage.py seed_demo --generate-password || true
  DJANGO_DEBUG=true python manage.py seed_demo --authority-only --generate-password || true
  DJANGO_DEBUG=true python manage.py seed_staff --generate-password || true
  DJANGO_DEBUG=true python manage.py seed_scenarios || true
fi

exec "$@"
