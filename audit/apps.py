from django.apps import AppConfig
from django.db.models.signals import post_save


class AuditConfig(AppConfig):
    name = 'audit'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from portal.models import AuditEvent
        from .signals import seal_new_event
        post_save.connect(seal_new_event, sender=AuditEvent, dispatch_uid='audit-seal-new-event')
