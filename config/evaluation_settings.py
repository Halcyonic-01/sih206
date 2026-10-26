"""Synthetic evaluation only. Real API keys still come from the private environment."""
from config.rehearsal_settings import *  # noqa: F403,F401
# Keep evaluation logs/quota separate from the browser rehearsal and earlier measurements.
BASE_DIR = PROJECT_ROOT / 'data' / 'semifinal-evaluation'
(BASE_DIR / 'data').mkdir(parents=True, exist_ok=True)
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'data' / 'portal.sqlite3'}}
MEDIA_ROOT = BASE_DIR / 'data' / 'documents'
AI_ENABLED = True
OCR_ENABLED = True
