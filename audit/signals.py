from .chain import seal_pending


def seal_new_event(sender, instance, created, raw=False, **kwargs):
    # raw=True is fixture loading; those events are sealed later by `seal_audit_chain`.
    if created and not raw:
        seal_pending(new_event_id=instance.pk)
