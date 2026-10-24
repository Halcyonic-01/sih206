from django.http import HttpResponse, JsonResponse

MESSAGE = 'Too many failed sign-in attempts. Wait before trying again.'


def lockout_response(request, original_response=None, credentials=None):
    """django-axes lockout answer: the API envelope for /api/, plain text elsewhere (no username echoed)."""
    if request.path.startswith('/api/'):
        return JsonResponse({'detail': MESSAGE, 'code': 'locked_out'}, status=429)
    return HttpResponse(MESSAGE, status=429, content_type='text/plain; charset=utf-8')
