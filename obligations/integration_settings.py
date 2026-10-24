"""Explicit localhost integration harness, not a replacement for K1 setup.

Uses the existing database/auth/settings and mounts only the owned API URLs.
No fixture providers or fake membership/parsing/notification hooks are installed.
"""
from config.settings import *  # noqa: F401,F403

ROOT_URLCONF = 'obligations.test_urls'
