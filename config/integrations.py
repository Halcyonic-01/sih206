"""Callables that settings hand to the release and obligation services (their "trusted ports").

Settings load before the apps, so each wrapper imports its implementation on first call. Tests replace them with
override_settings, as before.
"""


def release_facts(**kwargs):
    from casework.adapters import release_facts as implementation
    return implementation(**kwargs)


def clearance_evidence(actor, task, evidence_ref):
    from casework.adapters import clearance_evidence as implementation
    return implementation(actor, task, evidence_ref)


def completion_validator(upload):
    from casework.adapters import completion_validator as implementation
    return implementation(upload)


def notify(recipients, template, context, key):
    from notifications.service import notify as implementation
    return implementation(recipients, template, context, key)


def proof_receipts(actor, obligation):
    from obligations.services import reviewed_proof_receipts as implementation
    return implementation(actor, obligation)
