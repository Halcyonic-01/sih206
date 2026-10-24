"""WhiteNoise hooks (kept free of Django imports so settings.py can import them)."""


def static_headers(headers, path, url):
    """The built index.html must never be cached, or users keep an old app shell."""
    if str(path).endswith('.html'):
        headers['Cache-Control'] = 'no-store'


def immutable_assets(path, url):
    """Vite writes content-hashed files under /assets/, which can be cached for a year."""
    return url.startswith('/assets/')
