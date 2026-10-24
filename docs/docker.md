# Docker Compose (K10)

```bash
docker compose up --build        # http://localhost:8010/
```

First start creates the synthetic demo accounts and scenario records. Passwords are generated and stored in the
`portal-data` volume; they are never printed:

```bash
docker compose exec web cat data/demo-credentials.txt data/authority-credentials.txt data/staff-credentials.txt
```

* `web`: gunicorn serving Django, the React build (WhiteNoise) and the API; health check on `/api/health/`.
* `scheduler`: the same image looping `send_notifications` every 5 minutes and `run_due_rules` once per UTC day.
* `mailpit` (optional): `docker compose --profile mail up --build`, then set `EMAIL_HOST=mailpit EMAIL_PORT=1025
  EMAIL_USE_TLS=false` in `.env`; the inbox is at http://localhost:8025/.
* Configuration: copy `.env.example` to `.env`; Compose reads it for the `${...}` variables. A random
  `DJANGO_SECRET_KEY` is created in the volume when you do not set one. For anything other than localhost set
  `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECURE_COOKIES=true` and put TLS in front.
* Data lives in the `portal-data` volume (SQLite and uploaded PDFs). `docker compose down` keeps it;
  `docker compose down -v` deletes it.
* This is a demo packaging with synthetic data. Stage 3 replaces SQLite and local files with PostgreSQL and
  object storage behind Nginx with TLS.
