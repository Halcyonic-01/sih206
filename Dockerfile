# One image: React build (stage 1) served by Django + WhiteNoise under gunicorn (stage 2).
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY . .
COPY --from=frontend /app/frontend/dist ./frontend/dist
# Static files for the legacy pages and the API docs (a throwaway key is enough for this build step).
RUN DJANGO_DEBUG=false DJANGO_SECRET_KEY=build-only-not-used-at-runtime python manage.py collectstatic --noinput -v 0 \
    && useradd --create-home --uid 10001 app \
    && mkdir -p data \
    && chown -R app:app data \
    && chmod +x docker/entrypoint.sh
USER app
ENV DJANGO_DEBUG=false
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/', timeout=4).status == 200 else 1)"
ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60", "--access-logfile", "-"]
