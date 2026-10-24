"""Serves the built React app for every route Django does not own (client-side routing)."""
from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

NOT_BUILT = (
    '<!doctype html><meta charset="utf-8"><title>React app not built</title>'
    '<body style="font-family:system-ui;max-width:40rem;margin:4rem auto;padding:0 1rem">'
    '<h1>The React app has not been built</h1>'
    '<p>Run <code>npm ci &amp;&amp; npm run build</code> in <code>frontend/</code>, or start the dev server '
    'with <code>npm run dev</code> and open <a href="http://localhost:5173/">http://localhost:5173/</a>.</p>'
    '<p>The API is available at <a href="/api/docs/">/api/docs/</a> and the previous interface at '
    '<a href="/legacy/">/legacy/</a>.</p>'
)


@require_GET
@never_cache
def spa(request, path=''):
    # A path that looks like a file (has an extension) and was not served by WhiteNoise is a real 404,
    # so missing images or scripts never come back as HTML.
    if '.' in path.rsplit('/', 1)[-1]:
        raise Http404
    index = settings.FRONTEND_DIST / 'index.html'
    if not index.is_file():
        return HttpResponse(NOT_BUILT, status=503)
    return HttpResponse(index.read_bytes(), content_type='text/html; charset=utf-8')


def static_headers(headers, path, url):
    """WhiteNoise hook: the built index.html is served directly only under /index.html."""
    if str(path).endswith('.html'):
        headers['Cache-Control'] = 'no-store'


def immutable_assets(path, url):
    """Vite writes content-hashed files under /assets/, which can be cached for a year."""
    return url.startswith('/assets/')
