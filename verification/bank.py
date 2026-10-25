"""Bank email confirmation from operator-reviewed contacts, never institution input."""
from datetime import timedelta
from decimal import Decimal
import secrets

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from portal import services
from portal.models import Instrument, ReviewObservation
from portal.notification_hook import notify_record
from portal.permissions import require_officer, scoped_instruments
from .models import BankConfirmation, VerificationEvidence


def token_for(request):
    return signing.dumps({'id': str(request.pk)}, salt='bank-confirmation-v1')


def from_token(token):
    if not isinstance(token, str) or len(token) > 512:
        raise ValueError('Invalid token')
    data = signing.loads(token, salt='bank-confirmation-v1', max_age=86400)
    return BankConfirmation.objects.get(pk=data['id'])


@transaction.atomic
def request_confirmation(actor, pk, version):
    require_officer(actor)
    item = scoped_instruments(actor).get(pk=pk)
    if actor.pk == item.created_by_id or item.status not in ('SUBMITTED', 'ACCEPTED') or item.released_at or item.superseded_at:
        raise ValidationError('Only independently submitted/current records can receive a bank request.')
    if type(version) is not int:
        raise ValidationError('A current integer version is required.')
    contact = settings.BANK_CONTACTS.get(item.ifsc, {})
    if contact.get('approved') is not True or not contact.get('source'):
        raise ValidationError('No operator-reviewed bank contact exists for this IFSC.')
    email = contact.get('email', '')
    validate_email(email)
    if len(contact['source']) > 200:
        raise ValidationError('Invalid bank contact provenance.')
    if not settings.BANK_CONFIRMATION_SIMULATED and (settings.DEBUG or not settings.BANK_PUBLIC_BASE_URL.startswith('https://')):
        raise ValidationError('Live bank confirmation requires production secrets, HTTPS and approved delivery configuration.')
    BankConfirmation.objects.filter(instrument=item, status__in=['PENDING', 'SENT'],
        expires_at__lt=timezone.now()).update(status='EXPIRED')
    BankConfirmation.objects.filter(instrument=item, status__in=['PENDING', 'SENT']).exclude(
        instrument_version=item.version).update(status='STALE')
    if BankConfirmation.objects.filter(instrument=item, status__in=['PENDING', 'SENT']).exists():
        raise services.WorkflowError('A bank request is already open.')
    if BankConfirmation.objects.filter(instrument=item, created_at__gte=timezone.now()-timedelta(days=1)).count() >= 3:
        raise ValidationError('Bank request daily limit reached.')
    before = services.snapshot(item)
    services._compare_and_update(item, version)
    request = BankConfirmation.objects.create(instrument=item, requested_by=actor, instrument_version=item.version,
        ifsc=item.ifsc, recipient_email=email, contact_source=contact['source'],
        simulated=settings.BANK_CONFIRMATION_SIMULATED, expires_at=timezone.now()+timedelta(hours=24))
    services.event(item, actor, 'BANK_CONFIRMATION_REQUESTED', before,
        'SIMULATED bank contact request' if request.simulated else 'Request to operator-reviewed bank contact')
    return request


LOCAL_BACKENDS = {'django.core.mail.backends.locmem.EmailBackend', 'django.core.mail.backends.console.EmailBackend',
                  'django.core.mail.backends.filebased.EmailBackend'}
LOCAL_SMTP_HOSTS = {'localhost', '127.0.0.1', '::1', 'mailpit'}  # mailpit: the Docker Compose catcher service


def local_email_only():
    """A simulated request may only reach a mailbox on this machine: memory, console, file, or a local catcher."""
    backend = settings.EMAIL_BACKEND
    return backend in LOCAL_BACKENDS or (backend == 'django.core.mail.backends.smtp.EmailBackend'
                                         and settings.EMAIL_HOST.strip().lower() in LOCAL_SMTP_HOSTS)


def deliver_requests():
    """Explicit worker only. Never returns tokens or OTPs to the officer or logs."""
    sent = 0
    for pk in list(BankConfirmation.objects.filter(status='PENDING', expires_at__gt=timezone.now())
                   .values_list('pk', flat=True)[:100]):
        with transaction.atomic():
            row = BankConfirmation.objects.select_for_update().get(pk=pk)
            if row.status != 'PENDING':
                continue
            row.delivery_attempts += 1
            otp = f'{secrets.randbelow(1000000):06d}'
            row.otp_hash = make_password(otp)
            try:
                if not row.simulated and (not settings.NOTIFICATION_EMAIL_ENABLED or
                    settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend'):
                    raise ValueError('LIVE_EMAIL_NOT_CONFIGURED')
                if row.simulated and not local_email_only():
                    raise ValueError('SIMULATION_REQUIRES_LOCAL_EMAIL')
                link = settings.BANK_PUBLIC_BASE_URL.rstrip('/') + '/bank/confirm/' + token_for(row) + '/'
                prefix = 'SIMULATED ' if row.simulated else ''
                if send_mail(prefix+'Bank confirmation request',
                    f'{prefix}Deposit confirmation. Open {link}\nOne-time code: {otp}\nExpires in 24 hours. '
                    'Do not forward this link or code.', settings.DEFAULT_FROM_EMAIL, [row.recipient_email]) != 1:
                    raise ValueError('EMAIL_NOT_ACCEPTED')
                row.status, row.last_error = 'SENT', ''
                sent += 1
            except Exception:
                row.last_error = 'DELIVERY_FAILED'
                if row.delivery_attempts >= 5:
                    row.status = 'FAILED'
            row.save(update_fields=['delivery_attempts', 'otp_hash', 'status', 'last_error'])
    return sent


def respond(token, otp, fields):
    request_id = from_token(token).pk
    with transaction.atomic():
        row = BankConfirmation.objects.select_for_update().select_related('instrument').get(pk=request_id)
        if row.status != 'SENT' or row.expires_at <= timezone.now() or row.otp_attempts >= 5:
            raise ValidationError('This confirmation is expired, used or unavailable.')
        if not check_password(str(otp), row.otp_hash):
            row.otp_attempts += 1
            if row.otp_attempts >= 5:
                row.status = 'LOCKED'
            row.save(update_fields=['otp_attempts', 'status'])
            return False
        item = Instrument.objects.get(pk=row.instrument_id)
        if item.version != row.instrument_version:
            raise services.WorkflowError('The deposit changed. Ask the officer for a fresh request.')
        required = {'authentic', 'reference', 'amount', 'issue_date', 'maturity_date', 'ifsc', 'lien_marked', 'holder_names', 'loans_or_mortgage'}
        if not isinstance(fields, dict) or set(fields) != required or any(not isinstance(value, str) or len(value) > 250 for value in fields.values()):
            raise ValidationError('Complete every bank confirmation field.')
        if any(fields[key] not in ('yes', 'no') for key in ('authentic', 'lien_marked', 'loans_or_mortgage')):
            raise ValidationError('Answer yes or no for the bank declarations.')
        from datetime import date
        try:
            amount = Decimal(fields['amount'])
            if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2:
                raise ValueError()
            date.fromisoformat(fields['issue_date'])
            date.fromisoformat(fields['maturity_date'])
        except Exception:
            raise ValidationError('Provide a positive INR amount and ISO dates.') from None
        match = fields['authentic'] == 'yes' and fields['reference'].strip() == item.reference and amount == item.amount
        match = match and fields['issue_date'] == str(item.issue_date) and fields['maturity_date'] == str(item.maturity_date)
        match = match and fields['ifsc'].upper() == item.ifsc and fields['holder_names'].strip().casefold() == item.holder_names.strip().casefold()
        match = match and fields['lien_marked'] == 'yes' and fields['loans_or_mortgage'] == 'no'
        before = services.snapshot(item)
        changes = {'verification_level': 'DISCREPANCY'} if not match else (
            {} if row.simulated or item.observations.filter(severity='BLOCKING', resolved_at__isnull=True).exists()
            else {'verification_level': 'CONFIRMED'})
        services._compare_and_update(item, row.instrument_version, **changes)
        if not match and item.documents.exists():
            ReviewObservation.objects.create(instrument=item, document=item.documents.first(),
                reviewer=row.requested_by, severity='BLOCKING',
                comment=('SIMULATED ' if row.simulated else '')+'Bank response discrepancy. Review the confirmation evidence before acceptance.')
        VerificationEvidence.objects.create(instrument=item, actor=row.requested_by, instrument_version=item.version,
            method='SIMULATED_BANK' if row.simulated else 'BANK_CONFIRMATION',
            result=('SIMULATED_MATCH' if row.simulated else 'CONFIRMED') if match else 'DISCREPANCY',
            source=f'{row.ifsc}: {row.contact_source}'[:200], fields_observed=fields)
        row.status, row.response, row.completed_at = 'COMPLETED', fields, timezone.now()
        row.otp_hash = ''
        row.save(update_fields=['status', 'response', 'completed_at', 'otp_hash'])
        services.event(item, row.requested_by, 'BANK_CONFIRMATION_RECEIVED', before,
            'SIMULATED response' if row.simulated else 'Bank mailbox confirmation response')
        if not match:
            notify_record(item, 'verification_discrepancy')
        return True
