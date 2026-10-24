import hashlib
import os
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.core.exceptions import ImproperlyConfigured

from .envfile import load_env_file
from .staticrules import immutable_assets, static_headers

BASE_DIR = Path(__file__).resolve().parent.parent
# Optional local .env (git-ignored). Variables already set in the real environment take precedence.
load_env_file(BASE_DIR / '.env')
DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() == 'true'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError('Set DJANGO_SECRET_KEY when DJANGO_DEBUG=false.')
    SECRET_KEY = 'local-synthetic-demo-only-do-not-deploy'
if not DEBUG and SECRET_KEY.startswith('replace-with'):
    raise RuntimeError('DJANGO_SECRET_KEY still has the placeholder from .env.example. Generate a real one.')
ALLOWED_HOSTS = [host.strip() for host in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
                 if host.strip()]


def env_bool(name, default):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def env_int(name, default, minimum=0):
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        raise ImproperlyConfigured(f'{name} must be an integer.') from None
    if value < minimum:
        raise ImproperlyConfigured(f'{name} must be at least {minimum}.')
    return value

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'drf_spectacular', 'drf_spectacular_sidecar', 'axes',
    'portal', 'obligations', 'access', 'notifications', 'audit', 'scenarios',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'portal.middleware.RequestIdMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'axes.middleware.AxesMiddleware',
    'access.middleware.AccessLogMiddleware',
    'portal.middleware.SecurityHeadersMiddleware',
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
                         # IMMEDIATE takes the write lock at BEGIN, so concurrent writers queue instead of failing,
                         # and the audit hash chain is always extended by one writer at a time.
                         'OPTIONS': {'timeout': 20, 'transaction_mode': 'IMMEDIATE'}}}
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
# The legacy Django-template UI lives under /legacy/ until 28 Oct 2026; the React app owns /.
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'instrument_list'
LOGOUT_REDIRECT_URL = 'login'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 7200
SESSION_COOKIE_SECURE = env_bool('DJANGO_SECURE_COOKIES', False)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
# React reads the CSRF cookie and sends it back in X-CSRFToken, so this cookie must not be HttpOnly.
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',')
                        if origin.strip()]

# Transport and browser hardening. Production switches these on with environment variables;
# local HTTP demos keep working with the defaults.
SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', False)
SECURE_HSTS_SECONDS = env_int('DJANGO_HSTS_SECONDS', 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = False
if env_bool('DJANGO_BEHIND_TLS_PROXY', False):
    # Only enable behind a proxy that overwrites X-Forwarded-Proto.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
# The PDF viewer in the React app embeds our own documents, so framing is allowed for the same origin only.
X_FRAME_OPTIONS = 'SAMEORIGIN'
USE_X_FORWARDED_HOST = False

# Lockout after repeated failed sign-ins (PS scenario 8: "login locks after 5 failures").
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]
AXES_ENABLED = env_bool('AXES_ENABLED', True)
AXES_FAILURE_LIMIT = env_int('AXES_FAILURE_LIMIT', 5, minimum=1)
AXES_COOLOFF_TIME = timedelta(minutes=env_int('AXES_COOLOFF_MINUTES', 15, minimum=1))
AXES_LOCKOUT_PARAMETERS = [['username', 'ip_address']]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_CALLABLE = 'portal.api.lockout.lockout_response'
AXES_USERNAME_FORM_FIELD = 'username'
AXES_IPWARE_PROXY_COUNT = env_int('AXES_PROXY_COUNT', 0) or None
AXES_IPWARE_META_PRECEDENCE_ORDER = (
    ('HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR') if AXES_IPWARE_PROXY_COUNT else ('REMOTE_ADDR',))

# React build served by Django on one port (no separate web server needed for the review).
FRONTEND_DIST = BASE_DIR / 'frontend' / 'dist'
STATIC_ROOT = BASE_DIR / 'staticfiles'
WHITENOISE_ROOT = FRONTEND_DIST if FRONTEND_DIST.is_dir() else None
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG
WHITENOISE_ADD_HEADERS_FUNCTION = static_headers
WHITENOISE_IMMUTABLE_FILE_TEST = immutable_assets

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['portal.api.authentication.ApiSessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser', 'rest_framework.parsers.MultiPartParser',
                               'rest_framework.parsers.FormParser'],
    'EXCEPTION_HANDLER': 'portal.api.exceptions.exception_handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'portal.api.pagination.StandardPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_THROTTLE_RATES': {'login': os.environ.get('API_LOGIN_THROTTLE', '30/min')},
    'UNAUTHENTICATED_USER': 'django.contrib.auth.models.AnonymousUser',
}
SPECTACULAR_SETTINGS = {
    'TITLE': 'AICTE Security Deposit / FDR Portal API',
    'DESCRIPTION': 'Session-authenticated JSON API for the React app. Writes need the X-CSRFToken header '
                   'and the record `version` (stale versions return 409). SIH problem statement 26265.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': r'/api',
    'COMPONENT_SPLIT_REQUEST': True,
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',
}
# /api/docs/ is open in local DEBUG mode; otherwise only signed-in users can read it.
API_DOCS_PUBLIC = env_bool('API_DOCS_PUBLIC', DEBUG)
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# Email: the console backend in local DEBUG mode; set EMAIL_HOST (and credentials) for real SMTP.
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND') or (
    'django.core.mail.backends.console.EmailBackend' if not os.environ.get('EMAIL_HOST')
    else 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = env_int('EMAIL_PORT', 587)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = env_bool('EMAIL_USE_SSL', False)
EMAIL_TIMEOUT = env_int('EMAIL_TIMEOUT', 10, minimum=1)
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'AICTE Deposit Portal <no-reply@localhost>')
# Used to build links inside emails. Set to the public https address when deployed.
PORTAL_BASE_URL = os.environ.get('PORTAL_BASE_URL', 'http://127.0.0.1:8010')
# Try to send emails right after the event commits (the scheduled send_notifications command retries failures).
NOTIFY_SEND_ON_COMMIT = env_bool('NOTIFY_SEND_ON_COMMIT', True)

# Key for the audit hash chain (HMAC). Anyone who can only edit the database cannot recompute a valid chain
# without it. Set AUDIT_CHAIN_KEY in production; the fallback is derived from SECRET_KEY.
AUDIT_CHAIN_KEY = os.environ.get('AUDIT_CHAIN_KEY') or hashlib.sha256(('audit-chain|' + SECRET_KEY).encode()).hexdigest()

# Deliberate: same-origin framing is required by the in-app PDF viewer; HSTS preload is an explicit opt-in
# that cannot be undone quickly, so it stays off until AICTE decides on it.
# drf-spectacular warnings are reported by a separate CI step so a missing schema hint never blocks a merge.
SILENCED_SYSTEM_CHECKS = ['security.W019', 'security.W021', 'drf_spectacular.W001', 'drf_spectacular.W002']
