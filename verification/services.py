"""Synthetic reconciliation: matching never establishes bank authenticity."""
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
from .models import StatementImport, StatementLine, VerificationEvidence


def record_review(actor, item, reason):
    item.verification_level = Instrument.VerificationLevel.REVIEWED
    item.save(update_fields=['verification_level'])
    VerificationEvidence.objects.create(instrument=item, actor=actor, instrument_version=item.version,
        method='OFFICER_REVIEW', result='REVIEWED', source=reason[:200], fields_observed={})


def parse_statement(content):
    if len(content) > 1024 * 1024:
        raise ValidationError('Statement CSV must be at most 1 MB.')
    try:
        reader = csv.DictReader(StringIO(content.decode('utf-8-sig')), strict=True)
        if reader.fieldnames != ['utr', 'amount', 'value_date']:
            raise ValueError('headers')
        rows = []
        for number, row in enumerate(reader, 1):
            if number > 1000 or None in row or any(v is None for v in row.values()):
                raise ValueError('rows')
            amount = Decimal(row['amount'])
            if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2 or amount > Decimal('999999999999.99'):
                raise ValueError('amount')
            utr = row['utr'].strip().upper()
            day = date.fromisoformat(row['value_date'])
            if not utr or len(utr) > 100 or day.isoformat() != row['value_date']:
                raise ValueError('values')
            rows.append({'number': number, 'utr': utr, 'amount_paise': int(amount * 100), 'value_date': day})
        if not rows:
            raise ValueError('empty')
        return rows
    except (UnicodeError, ValueError, InvalidOperation, csv.Error):
        raise ValidationError('Use UTF-8 CSV headers utr,amount,value_date and positive two-decimal amounts.') from None


def plan_matches(actor, content):
    require_officer(actor)
    rows = parse_statement(content)
    duplicates = Counter(row['utr'] for row in rows)
    visible = scoped_instruments(actor).filter(mode='RTGS', superseded_at__isnull=True, released_at__isnull=True)
    planned = []
    for row in rows:
        candidates = list(visible.filter(utr__iexact=row['utr'])[:2])
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
            changes = {'verification_level': 'DISCREPANCY'} if row['result'] == 'DISCREPANCY' else {}
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
    prefixes = set(getattr(settings, 'VERIFICATION_ISSUER_PREFIXES', ()))
    if not item.ifsc or item.ifsc[:4] not in prefixes:
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
