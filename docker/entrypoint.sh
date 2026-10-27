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

# Document encryption key: same pattern. In a real deployment set DOCUMENT_ENCRYPTION_KEY from a secret store; a key kept in
# the data volume is only as safe as the volume, so it does not protect a copied volume snapshot.
if [ -z "${DOCUMENT_ENCRYPTION_KEY:-}" ]; then
  if [ ! -s data/.document_key ]; then
    python -c "from config.documentkey import generate_key; print(generate_key())" > data/.document_key
    chmod 600 data/.document_key
  fi
  DOCUMENT_ENCRYPTION_KEY="$(cat data/.document_key)"
  export DOCUMENT_ENCRYPTION_KEY
fi

# Letter-signing key (Ed25519, signs the facts in each letter's QR). Same caveat: set LETTER_SIGNING_KEY from a secret store in real use.
if [ -z "${LETTER_SIGNING_KEY:-}" ]; then
  if [ ! -s data/.letter_key ]; then
    python -c "from config.documentkey import generate_key; print(generate_key())" > data/.letter_key
    chmod 600 data/.letter_key
  fi
  LETTER_SIGNING_KEY="$(cat data/.letter_key)"
  export LETTER_SIGNING_KEY
fi

python manage.py migrate --noinput
python manage.py seal_audit_chain
# Encrypt documents stored before encryption was on (idempotent); a problem is reported but does not stop start-up.
python manage.py encrypt_documents || echo "encrypt_documents reported a problem; see above"

# Synthetic demo accounts on the first start only. Generated passwords are written to the data volume
# (never printed); read them with: docker compose exec web cat data/demo-credentials.txt
if [ "${SEED_DEMO:-true}" = "true" ] && [ ! -f data/demo-credentials.txt ]; then
  echo "First start: creating synthetic demo accounts and scenario records"
  DJANGO_DEBUG=true python manage.py seed_demo --generate-password || true
  DJANGO_DEBUG=true python manage.py seed_demo --authority-only --generate-password || true
  DJANGO_DEBUG=true python manage.py seed_staff --generate-password || true
  DJANGO_DEBUG=true python manage.py seed_scenarios || true
  DJANGO_DEBUG=true python manage.py seed_review || true
fi

exec "$@"
