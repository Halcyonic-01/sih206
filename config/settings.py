import os
import json
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
OCR_ENABLED = os.environ.get('OCR_ENABLED', 'true').lower() == 'true'
OCR_TESSERACT = os.environ.get('OCR_TESSERACT', '')
OCR_PDFTOPPM = os.environ.get('OCR_PDFTOPPM', '')
YASH_NOTIFY_BACKEND = 'notifications.services.notify'
NOTIFICATION_EMAIL_ENABLED = os.environ.get('NOTIFICATION_EMAIL_ENABLED', 'false').lower() == 'true'
EMAIL_BACKEND = os.environ.get('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.locmem.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'true').lower() == 'true'
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'portal@example.invalid')
BANK_CONTACTS = json.loads(os.environ.get('BANK_CONTACTS_JSON', '{}'))
BANK_CONFIRMATION_SIMULATED = os.environ.get('BANK_CONFIRMATION_SIMULATED', 'true').lower() == 'true'
BANK_PUBLIC_BASE_URL = os.environ.get('BANK_PUBLIC_BASE_URL', 'http://127.0.0.1:8010')
DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() == 'true'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError('Set DJANGO_SECRET_KEY when DJANGO_DEBUG=false.')
    SECRET_KEY = 'local-synthetic-demo-only-do-not-deploy'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'portal', 'obligations', 'rest_framework', 'verification', 'ai', 'notifications',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'portal.middleware.OperationalSafetyMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'
(BASE_DIR / 'data').mkdir(exist_ok=True)
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3',
                         'NAME': BASE_DIR / 'data' / 'portal.sqlite3',
                         'OPTIONS': {'timeout': 20}}}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'en-in'
TIME_ZONE = os.environ.get('BUSINESS_TIMEZONE', 'Asia/Kolkata')
try:
    ZoneInfo(TIME_ZONE)
except (ZoneInfoNotFoundError, ValueError):
    raise ImproperlyConfigured('BUSINESS_TIMEZONE must be a valid IANA timezone.') from None
try:
    REMINDER_DAYS = tuple(int(value.strip()) for value in os.environ.get('REMINDER_DAYS', '30,15,7').split(','))
except ValueError:
    raise ImproperlyConfigured('REMINDER_DAYS must be comma-separated positive integers.') from None
if not REMINDER_DAYS or any(day < 1 for day in REMINDER_DAYS):
    raise ImproperlyConfigured('REMINDER_DAYS must contain positive integer day thresholds.')
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
if (BASE_DIR / 'frontend' / 'dist').exists():
    STATICFILES_DIRS.append(BASE_DIR / 'frontend' / 'dist')
# No MEDIA_URL route: all document reads go through an ownership-checked view.
MEDIA_ROOT = BASE_DIR / 'data' / 'documents'
try:
    MAX_UPLOAD_BYTES = int(os.environ.get('MAX_UPLOAD_MB', '10')) * 1024 * 1024
except ValueError:
    raise ImproperlyConfigured('MAX_UPLOAD_MB must be a positive integer.') from None
if MAX_UPLOAD_BYTES <= 0:
    raise ImproperlyConfigured('MAX_UPLOAD_MB must be a positive integer.')
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'instrument_list'
LOGOUT_REDIRECT_URL = 'login'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 7200
SESSION_COOKIE_SECURE = os.environ.get('DJANGO_SECURE_COOKIES', 'false').lower() == 'true'
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AI_ENABLED = os.environ.get('AI_ENABLED', 'false').lower() == 'true'
AI_MODEL = 'claude-opus-5-5'
