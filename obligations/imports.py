"""S4 preview then atomic commit; explicit SIMULATED institution data only."""
from datetime import timedelta
import hashlib
import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from portal.models import Institution
from portal.permissions import require_officer
from portal.services import WorkflowError
from .csv_validation import ExistingIdentity, validate_institution_csv
from .models import CsvImport
from .services import create_institution, expected_version, reason_text


def identities():
    rows = list(Institution.objects.order_by('pk').values_list('code', 'deposit_profile__aicte_id'))
    fingerprint = hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()
    return tuple(ExistingIdentity(aicte_id=aid, institution_code=code) for code, aid in rows), fingerprint


def preview(actor, content):
    require_officer(actor)
    context, fingerprint = identities()
    result = validate_institution_csv(content, existing_identities=context)
    result['preview_id'] = None
    if result['status'] == 'VALID':
        item = CsvImport.objects.create(actor=actor, source=content,
            source_sha256=result['source_sha256'], identity_sha256=fingerprint,
            expires_at=timezone.now() + timedelta(minutes=30))
        result.update(preview_id=item.pk, version=item.version, expires_at=item.expires_at.isoformat())
    return result


@transaction.atomic
def commit(actor, preview_id, version, reason):
    require_officer(actor)
    expected_version(version)
    reason = reason_text(reason)
    item = get_object_or_404(CsvImport, pk=preview_id, actor=actor)
    if item.version != version or item.committed_at is not None or item.expires_at <= timezone.now():
        raise WorkflowError('Preview expired, changed or already consumed. Preview again.')
    context, fingerprint = identities()
    if fingerprint != item.identity_sha256:
        raise WorkflowError('Institution identities changed. Preview again.')
    content = bytes(item.source)
    if hashlib.sha256(content).hexdigest() != item.source_sha256:
        raise WorkflowError('Preview source changed. Preview again.')
    result = validate_institution_csv(content, existing_identities=context)
    if result['status'] != 'VALID':
        raise ValidationError('The complete file must still be valid; partial import is forbidden.')
    # Compare-and-swap claims this preview in the same transaction as all rows/audits.
    if not CsvImport.objects.filter(pk=item.pk, version=version, committed_at__isnull=True).update(
            version=version + 1, committed_at=timezone.now()):
        raise WorkflowError('Preview was already consumed.')
    created = []
    for row in result['valid_rows']:
        values = dict(row['values'])
        values.pop('data_classification')
        values['code'] = values.pop('institution_code')
        values['name'] = values.pop('institution_name')
        created.append(create_institution(actor, values, 'SIMULATED CSV import: ' + reason[:1970]).institution_id)
    item.created_ids = created
    item.source = b''  # Retain source hash/provenance; no need to retain contacts twice.
    item.save(update_fields=['created_ids', 'source'])
    return {'simulation_label': 'SIMULATED', 'status': 'COMMITTED', 'created_ids': created,
            'version': version + 1, 'source_sha256': item.source_sha256}
