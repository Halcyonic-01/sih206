from django.apps import AppConfig


class VerificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'verification'

    def ready(self):
        from django.db.models.signals import post_save
        from portal.models import Document
        post_save.connect(fingerprint_new_document, sender=Document, dispatch_uid='verification-fingerprint-new-document')


def fingerprint_new_document(sender, instance, created, raw=False, **kwargs):
    """After a document commits, compute its first-page fingerprint (best effort; never blocks or fails an upload)."""
    if not created or raw:
        return
    from django.db import transaction

    def run():
        from . import fingerprint
        try:
            fingerprint.ensure(instance)
        except Exception:   # pragma: no cover - the upload has already succeeded
            pass
    transaction.on_commit(run)
