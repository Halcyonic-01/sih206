"""Synthetic reconciliation: a statement match confirms the deposit fields, labelled SIMULATED; never bank authenticity."""
from collections import Counter
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
from io import StringIO

from django.core.exceptions import ValidationError
from django.db import transaction

from portal import services as records
from portal.models import Instrument, ReviewObservation
from portal.notification_hook import notify_record
from portal.permissions import require_officer, role, scoped_instruments
from . import statement_formats
from .models import StatementImport, StatementLine, VerificationEvidence


def record_review(actor, item, reason):
    if item.verification_level != Instrument.VerificationLevel.CONFIRMED:
        item.verification_level = Instrument.VerificationLevel.REVIEWED
        item.save(update_fields=['verification_level'])
    VerificationEvidence.objects.create(instrument=item, actor=actor, instrument_version=item.version,
        method='OFFICER_REVIEW', result='REVIEWED', source=reason[:200], fields_observed={})


def parse_statement(content):
    """Rows of a statement in any supported format (CSV, MT940, CAMT.053); see statement_formats.py."""
    return statement_formats.parse(content).rows


def describe_statement(content):
    """Format name plus the quarantined (malformed) and ignored (not a receipt) entries, for the preview."""
    return statement_formats.parse(content).summary()


def plan_matches(actor, content):
    require_officer(actor)
    rows = parse_statement(content)
    duplicates = Counter(row['utr'] for row in rows)
    visible = scoped_instruments(actor).filter(mode='RTGS', superseded_at__isnull=True, released_at__isnull=True)
    planned = []
    for row in rows:
        candidates = []
        for reference in [row['utr'], *row.get('alt_utrs', [])]:  # the line's main reference first, then its other references
            candidates = list(visible.filter(utr__iexact=reference)[:2])
            if candidates:
                row = row | {'utr': reference}
                break
        item = candidates[0] if len(candidates) == 1 else None
        if duplicates[row['utr']] > 1 or len(candidates) > 1:
            result = 'AMBIGUOUS'
            item = None
        elif item is None:
            result = 'UNMATCHED'
        elif item.amount_paise != row['amount_paise'] or item.issue_date != row['value_date']:
            result = 'DISCREPANCY'
        else:
            result = 'SIMULATED_MATCH'
        row = {key: value for key, value in row.items() if key != 'alt_utrs'}
        planned.append(row | {'instrument_id': item.pk if item else None,
                               'version': item.version if item else None, 'result': result})
    return planned


@transaction.atomic
def import_statement(actor, content, source, versions):
    require_officer(actor)
    if not isinstance(source, str) or not source.strip() or len(source) > 200:
        raise ValidationError('A synthetic source label of at most 200 characters is required.')
    digest = hashlib.sha256(content).hexdigest()
    existing = StatementImport.objects.filter(source=source.strip(), sha256=digest).first()
    if existing:
        return existing, True
    planned = plan_matches(actor, content)
    if not isinstance(versions, dict):
        raise ValidationError('Preview versions are required.')
    batch = StatementImport.objects.create(source=source.strip(), sha256=digest,
                                           imported_by=actor, simulated=True)
    for row in planned:
        item = None
        if row['instrument_id']:
            item = scoped_instruments(actor).get(pk=row['instrument_id'])
            expected = versions.get(str(item.pk))
            if type(expected) is not int:
                raise ValidationError('A preview version is required for each matched record.')
            before = records.snapshot(item)
            # Plan Y6 / F3: a UTR + amount + date match records statement confirmation (level 3); the evidence row
            # keeps method SIMULATED_STATEMENT, so the record shows where the confirmation came from.
            changes = {'verification_level': {'DISCREPANCY': 'DISCREPANCY', 'SIMULATED_MATCH': 'CONFIRMED'}[row['result']]}
            records._compare_and_update(item, expected, **changes)
        line = StatementLine.objects.create(batch=batch, number=row['number'], utr=row['utr'],
            amount_paise=row['amount_paise'], value_date=row['value_date'], result=row['result'], instrument=item)
        if item:
            VerificationEvidence.objects.create(instrument=item, actor=actor, instrument_version=item.version,
                method='SIMULATED_STATEMENT', result=row['result'], source=source.strip(), statement_line=line,
                fields_observed={'utr': row['utr'], 'amount_paise': row['amount_paise'],
                    'value_date': row['value_date'].isoformat(), 'simulated': True,
                    'declared_amount_paise': item.amount_paise, 'declared_issue_date': item.issue_date.isoformat()})
            if row['result'] == 'DISCREPANCY':
                document = item.documents.first()
                if document:
                    ReviewObservation.objects.create(instrument=item, document=document, reviewer=actor,
                        severity='BLOCKING', comment='SIMULATED statement mismatch: inspect amount and payment date.')
                notify_record(item, 'verification_discrepancy')
            records.event(item, actor, 'SIMULATED_RECONCILIATION', before,
                          'Synthetic statement evidence; not independent bank confirmation.')
    return batch, False


def checks(actor, item):
    # A prefix list is not a bank/branch directory. Missing data stays unknown.
    findings = []
    from django.conf import settings
    from . import bankmaster
    prefixes = set(getattr(settings, 'VERIFICATION_ISSUER_PREFIXES', ()))
    if bankmaster.directory_loaded():
        findings.extend(bankmaster.issuer_findings(item))   # a loaded IFSC directory replaces the prefix list
    elif not item.ifsc or item.ifsc[:4] not in prefixes:
        findings.append({'code': 'ISSUER_UNKNOWN', 'severity': 'warning',
                         'explanation': 'Issuer is not in the configured reviewed prefix list; identity needs review.'})
    else:
        findings.append({'code': 'ISSUER_UNCONFIRMED', 'severity': 'warning',
                         'explanation': 'IFSC format alone does not establish bank or branch identity.'})
    if role(actor) == 'officer':
        candidates = scoped_instruments(actor).exclude(institution_id=item.institution_id)
        reference = item.reference.strip().casefold()
        bank = item.bank.strip().casefold()
        issuer = item.ifsc.strip().upper()
        duplicate = any(ref.strip().casefold() == reference and
            (code.strip().upper() == issuer if issuer else name.strip().casefold() == bank)
            for ref, name, code in candidates.values_list('reference', 'bank', 'ifsc').iterator())
        if duplicate:
            findings.append({'code': 'CROSS_INSTITUTION_POSSIBLE_DUPLICATE', 'severity': 'warning',
                'explanation': 'A visible submitted record has matching issuer/reference details. Review required.'})
    return findings


def field_provenance(item):
    """Per-field status for the record detail; see verification/provenance.py."""
    from .provenance import derive
    return derive(item, list(item.verification_evidence.all()),
                  list(item.audit_events.filter(action='OFFICER_CORRECTION')))
