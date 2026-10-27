"""Workflow adapter to the transactional notification outbox."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.module_loading import import_string


def notify_record(item, template):
    path = getattr(settings, 'YASH_NOTIFY_BACKEND', 'notifications.service.notify')
    if not path:
        # An installation may explicitly disable the adapter.
        return False
    recipients = list(get_user_model().objects.filter(is_active=True,
        userprofile__institution_id=item.institution_id).values_list('pk', flat=True))
    if template == 'record_submitted':
        from notifications.recipients import officers
        recipients = [user.pk for user in officers(item.institution)]
    template = {'record_submitted': 'instrument_submitted',
                'record_reviewed': 'instrument_accepted' if item.status == 'ACCEPTED' else 'instrument_changes_requested'}.get(template, template)
    queued = import_string(path)(recipients=recipients, template=template,
        context={'instrument_id': item.pk, 'reference': item.reference, 'url': f'/records/{item.pk}'},
        key=f'instrument:{item.pk}:{template}:v{item.version}')
    return bool(queued)
