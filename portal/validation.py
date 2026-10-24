"""Small deterministic checks over declared data; no PDF extraction or policy engine."""
from dataclasses import asdict, dataclass

from .models import Document, Instrument

CHECKS_VERSION = 'technical-v2'


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


def run_checks(instrument):
    return [finding for check in (check_document_present, check_possible_duplicate)
            if (finding := check(instrument)) is not None]


def checks_snapshot(instrument):
    return {'checks_version': CHECKS_VERSION,
            'deposit_checks_version': 'deposit-modes-v1',
            'technical_findings': [finding.as_dict() for finding in run_checks(instrument)]}
