"""Workflow adapter to the transactional notification outbox."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.module_loading import import_string


def notify_record(item, template):
    path = getattr(settings, 'YASH_NOTIFY_BACKEND', '')
    if not path:
        # An installation may explicitly disable the adapter.
        return False
    recipients = list(get_user_model().objects.filter(is_active=True,
        userprofile__institution_id=item.institution_id).values_list('pk', flat=True))
    if template == 'record_submitted':
        recipients = list(get_user_model().objects.filter(is_active=True,
            groups__name='Officer').values_list('pk', flat=True))
    import_string(path)(recipients=recipients, template=template,
        context={'instrument_id': item.pk, 'reference': item.reference},
        key=f'instrument:{item.pk}:{template}:v{item.version}')
    return True
