"""Explicit disposable semifinal environment; never points at DATABASE_URL.

Use --settings=config.rehearsal_settings. Private data and credentials live under
data/semifinal; the normal app's database/media/credentials are not modified.
"""
from config.settings import *  # noqa: F403,F401

PROJECT_ROOT = BASE_DIR
BASE_DIR = PROJECT_ROOT / 'data' / 'semifinal'
(BASE_DIR / 'data').mkdir(parents=True, exist_ok=True)
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'data' / 'portal.sqlite3'}}
MEDIA_ROOT = BASE_DIR / 'data' / 'documents'
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
NOTIFY_SEND_ON_COMMIT = False
NOTIFICATION_EMAIL_ENABLED = False
AI_ENABLED = False
OCR_ENABLED = False
PORTAL_BASE_URL = 'http://127.0.0.1:8011'
SAKSHAM_PUBLIC_BASE_URL = PORTAL_BASE_URL
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
CSRF_TRUSTED_ORIGINS = []
