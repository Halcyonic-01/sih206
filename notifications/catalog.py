"""Message templates. Plain text, short, and never more than a reference: details stay behind the sign-in.

Add a template here (K owns this file; open a pull request) or pass `subject` and `message` in the context and
use any template id: unregistered ids fall back to the generic template so a missing entry never blocks a feature.
Placeholders use str.format with the notify() context.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    subject: str
    body: str
    severity: str = 'info'
    email: bool = True


TEMPLATES = {
    # Y3: records
    'instrument_submitted': Template(
        'New submission to review: {reference}',
        'An institution submitted FDR {reference} for review. Open the portal to review it.'),
    'instrument_accepted': Template(
        'FDR {reference} accepted for tracking',
        'FDR {reference} was accepted for tracking. This is not bank verification.'),
    'instrument_changes_requested': Template(
        'Changes requested on FDR {reference}',
        'The officer asked for changes to FDR {reference}. Open the portal to see the observations.',
        'warning'),
    'document_integrity_failed': Template(
        'Stored document failed its integrity check: {reference}',
        'The stored file {document} on FDR {reference} no longer matches the checksum recorded at upload, '
        'so downloads were refused. Treat the document as unreliable and ask the institution to upload it again.',
        'critical'),
    # Y6: verification
    'verification_discrepancy': Template(
        'Statement mismatch on FDR {reference}',
        'A statement line did not match FDR {reference}. An officer needs to look at it.', 'critical'),
    'verification_confirmed': Template(
        'FDR {reference} confirmed against a statement',
        'A bank statement line matched FDR {reference} (simulated source in the demo).'),
    # S5: release case
    'release_requested': Template(
        'Release requested for FDR {reference}',
        'A release request was submitted for FDR {reference}. Clearance tasks are open.'),
    'clearance_assigned': Template(
        'Clearance needed ({unit}) for FDR {reference}',
        'A {unit} clearance task is waiting for your unit on FDR {reference}.'),
    'penalty_proposed': Template(
        'Penalty proposed on FDR {reference}',
        'A penalty assessment is waiting for a decision on FDR {reference}.', 'warning'),
    'release_second_signature': Template(
        'Second signature needed on FDR {reference}',
        'A first authority signature was recorded on the release of FDR {reference}. A different authority user must give '
        'the second signature before the release is authorised.', 'warning'),
    'release_decided': Template(
        'Release decision on FDR {reference}',
        'A decision was recorded on the release request for FDR {reference}.'),
    'noc_issued': Template(
        'Letter issued for FDR {reference}',
        'The NOC or sanction order for FDR {reference} is ready in the portal.'),
    # K6: scheduled rules
    'maturity_reminder': Template(
        'FDR {reference} matures in {days} days',
        'FDR {reference} matures on {maturity_date} (in {days} days). Plan the renewal.', 'warning'),
    'renewal_overdue': Template(
        'Renewal overdue: FDR {reference}',
        'FDR {reference} matured on {maturity_date} and has no accepted successor.', 'critical'),
    'penalty_review_due': Template(
        'Penalty review due: FDR {reference}',
        'FDR {reference} has been past maturity for {days} days. Review for a penalty (APH 7.7).', 'critical'),
    'proof_due_reminder': Template(
        'Deposit proof due: day {day} of 15',
        'Deposit proof for {institution} is due. Day {day} of 15 since intimation; penalty band: {band}.',
        'warning'),
    'sla_submission_pending': Template(
        'Submission waiting {days} days: FDR {reference}',
        'FDR {reference} has waited {days} days for review (limit {limit}).', 'warning'),
    'sla_correction_pending': Template(
        'Correction outstanding {days} days: FDR {reference}',
        'Requested changes on FDR {reference} are still open after {days} days.', 'warning'),
    'sla_clearance_pending': Template(
        'Clearance open {days} days: {unit} on FDR {reference}',
        'The {unit} clearance on FDR {reference} has been open for {days} days (limit {limit}).', 'warning'),
}

GENERIC = Template('{subject}', '{message}')


class _SafeDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'


def render(template_id, context):
    """Return (subject, body, severity, email_enabled). Missing placeholders stay visible, never raise."""
    template = TEMPLATES.get(template_id, GENERIC)
    values = _SafeDict({'subject': 'Notification', 'message': '', **(context or {})})
    subject = template.subject.format_map(values)[:200]
    body = template.body.format_map(values)
    return subject, body, (context or {}).get('severity', template.severity), template.email
