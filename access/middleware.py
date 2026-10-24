import re

from .logging import log_access
from .models import AccessLog

# Safety net: any successful GET that looks like a download or export is logged even if its view forgot to
# call log_access(). Views that do call it set request.access_logged, so nothing is written twice.
DOWNLOAD_LIKE = re.compile(r'(^|/)(download|export|reports?)(\b|[/._-])|\.(csv|xlsx|pdf)$', re.IGNORECASE)
IGNORED_PREFIXES = ('/api/docs/', '/api/schema/', '/api/redoc/', '/static/', '/assets/')


class AccessLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (request.method == 'GET' and response.status_code == 200
                and not getattr(request, 'access_logged', False)
                and getattr(request, 'user', None) is not None and request.user.is_authenticated
                and not request.path.startswith(IGNORED_PREFIXES)
                and DOWNLOAD_LIKE.search(request.path)):
            log_access(request, AccessLog.DOWNLOAD, detail='logged by middleware fallback')
        return response
