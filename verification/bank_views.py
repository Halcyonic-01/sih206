from django.core import signing
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from portal.services import WorkflowError
from .bank import from_token, respond
from .models import BankConfirmation


@never_cache
@ensure_csrf_cookie
@csrf_protect
@require_http_methods(['GET', 'POST'])
def confirmation(request, token):
    try:
        row = from_token(token)
        if row.status != 'SENT' or row.expires_at <= timezone.now():
            raise ValidationError('Request unavailable')
        if request.method == 'POST':
            fields = {key: request.POST.get(key, '') for key in ('authentic', 'reference', 'amount', 'issue_date',
                'maturity_date', 'ifsc', 'lien_marked', 'holder_names', 'loans_or_mortgage')}
            if not respond(token, request.POST.get('otp', ''), fields):
                return JsonResponse({'detail': 'Invalid code.'}, status=400)
            return JsonResponse({'detail': 'SIMULATED response recorded.' if row.simulated else 'Bank response recorded for officer review.'})
        response = render(request, 'bank_confirmation.html', {'simulated': row.simulated})
        response['Referrer-Policy'] = 'no-referrer'
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
    except WorkflowError:
        return JsonResponse({'detail': 'The deposit changed. Ask the officer for a new request.'}, status=409)
    except (signing.BadSignature, BankConfirmation.DoesNotExist, ValidationError, ValueError, KeyError):
        return JsonResponse({'detail': 'Confirmation unavailable. Check the link, code and required fields.'}, status=400)
