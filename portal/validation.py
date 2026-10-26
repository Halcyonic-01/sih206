"""Small deterministic checks over declared data; no PDF extraction or policy engine."""
import re
from dataclasses import asdict, dataclass

from django.conf import settings

from .models import Document, Instrument

CHECKS_VERSION = 'technical-v3'
# Where each AICTE-specific check comes from. Draft: the amounts and rules are not approved policy. They live here and
# not in the obligations RuleSet because that payload schema (v1) is fixed; moving them needs a schema v2.
AICTE_CHECK_RULES = {
    'HOLDER_NOT_AICTE': {'clause': 'APH 1.12(iv)-(v): joint FDR in the names of the Trust Secretary and AICTE',
                         'status': 'DRAFT_DEMO_NOT_APPROVED'},
    'LIEN_NOT_MARKED': {'clause': 'APH 1.12: the deposit is held by the Council (exact lien wording to be confirmed)',
                        'status': 'DRAFT_DEMO_NOT_APPROVED'},
}
_AICTE_NAME = re.compile(r'\baicte\b|all india council for technical education', re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    explanation: str
    values: dict

    def as_dict(self):
        return asdict(self)


def check_document_present(instrument):
    kind = {'FDR': Document.Kind.FDR, 'RTGS': Document.Kind.PAYMENT_PROOF,
            'RPGF': Document.Kind.RPGF_PROOF}[instrument.mode]
    if not instrument.documents.filter(kind=kind).exists():
        return Finding(
            code='FDR_DOCUMENT_REQUIRED' if instrument.mode == 'FDR' else 'DEPOSIT_DOCUMENT_REQUIRED', severity='blocking',
            explanation='Upload the deposit-mode supporting PDF before submitting or accepting this record.',
            values={'attached_document_count': 0},
        )
    return None


def check_possible_duplicate(instrument):
    # Scope FIRST. Return only this record's inputs, never another record's identity.
    duplicates = Instrument.objects.filter(institution_id=instrument.institution_id).exclude(pk=instrument.pk)
    # SQLite LOWER/TRIM handle ASCII only; use the same Unicode normalization
    # for both sides. Stream only scoped values; never expose another record.
    key = (instrument.bank.strip().casefold(), instrument.reference.strip().casefold())
    if any((bank.strip().casefold(), reference.strip().casefold()) == key
           for bank, reference in duplicates.values_list('bank', 'reference').iterator()):
        return Finding(
            code='POSSIBLE_DUPLICATE', severity='warning',
            explanation='Another record in this institution has the same bank and FDR reference '
                        '(ignoring letter case and surrounding spaces). Review possible duplication; '
                        'this warning does not establish fraud or block acceptance.',
            values={'bank': instrument.bank, 'reference': instrument.reference},
        )
    return None


def check_holder_names(instrument):
    """An FDR whose recorded holders do not include AICTE can be broken without the Council's involvement.

    Only a recorded value is judged: blank means "not recorded yet" and produces no finding.
    """
    names = (instrument.holder_names or '').strip()
    if instrument.mode != 'FDR' or not names or _AICTE_NAME.search(names):
        return None
    return Finding(
        code='HOLDER_NOT_AICTE', severity='warning',
        explanation='The recorded holder names do not include the Member Secretary, AICTE. A deposit held only in the '
                    "trust's name is not secured in favour of the Council. Compare the FDR document and ask the "
                    'institution to confirm. This is advisory and uses draft rules.',
        values={'holder_names': names, **AICTE_CHECK_RULES['HOLDER_NOT_AICTE']})


def check_lien_marked(instrument):
    """Only an explicit "no" is judged: unknown (not recorded, or a legacy record) is not treated as "no lien"."""
    if instrument.mode != 'FDR' or instrument.lien_marked is not False:
        return None
    blocking = getattr(settings, 'FDR_LIEN_CHECK_BLOCKING', False)
    return Finding(
        code='LIEN_NOT_MARKED', severity='blocking' if blocking else 'warning',
        explanation='The record says no lien is marked in favour of AICTE. '
                    + ('Acceptance is blocked until the lien is marked and the record is corrected.' if blocking
                       else 'This is advisory (draft rules); acceptance is not blocked.'),
        values={'lien_marked': False, 'blocks_acceptance': blocking, **AICTE_CHECK_RULES['LIEN_NOT_MARKED']})


def run_checks(instrument):
    return [finding for check in (check_document_present, check_possible_duplicate, check_holder_names, check_lien_marked)
            if (finding := check(instrument)) is not None]


def checks_snapshot(instrument):
    return {'checks_version': CHECKS_VERSION,
            'deposit_checks_version': 'deposit-modes-v1',
            'technical_findings': [finding.as_dict() for finding in run_checks(instrument)]}
