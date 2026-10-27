"""Release governance (P1-1): a second authority signature above an amount, and an approval tied to what was approved.

* **Approval levels.** A `RuleSet` with code `release-approval` may hold
  `{"label": ..., "approval_levels": [{"min_amount_paise": 100000000, "signatures": 2}]}`. The level that applies to the
  deposit being released is copied onto the case when it opens (`ReleaseCase.approval_policy`), so a later rule change does
  not alter an open case. With no such RuleSet the built-in draft applies: two signatures from ₹1 crore. Labelled
  DRAFT_DEMO_NOT_APPROVED like the other rules.
* **Basis fingerprint.** When the last required signature is recorded, a SHA-256 over the documents (hashes), clearance
  results, penalty decisions, rule and declarations is stored. Letter issue and completion refuse (409) if it no longer
  matches, so an approval cannot silently cover documents or decisions nobody approved. If the basis changes while only the
  first signature exists, that signature is voided and the next signer starts again.
* **Separate completer.** With `RELEASE_REQUIRE_DIFFERENT_COMPLETER=true`, the person who authorised cannot also record
  completion.
"""
import hashlib
import json

from django.conf import settings

from portal.models import Document

DRAFT_LABEL = 'DRAFT_DEMO_NOT_APPROVED'
DEFAULT_LEVELS = [{'min_amount_paise': 1_000_000_000, 'signatures': 2}]  # ₹1 crore = 10,000,000 rupees = 1,000,000,000 paise
RULESET_CODE = 'release-approval'


def policy_for(amount_paise, as_of):
    """The approval policy that applies to a release of `amount_paise`, ready to store on the case."""
    from obligations.models import RuleSet
    ruleset = (RuleSet.objects.filter(code=RULESET_CODE, effective_from__lte=as_of)
               .exclude(effective_to__lt=as_of).order_by('-version').first())
    levels, source, label = DEFAULT_LEVELS, 'built-in draft', DRAFT_LABEL
    if ruleset is not None and isinstance(ruleset.payload.get('approval_levels'), list):
        levels = ruleset.payload['approval_levels']
        source, label = f'ruleset {ruleset.code} v{ruleset.version}', ruleset.payload.get('label') or DRAFT_LABEL
    needed, threshold = 1, None
    for level in levels:
        minimum, signatures = level.get('min_amount_paise'), level.get('signatures')
        if type(minimum) is int and type(signatures) is int and 1 <= signatures <= 2 and amount_paise >= minimum \
                and signatures > needed:
            needed, threshold = signatures, minimum
    return {'required_signatures': needed, 'threshold_paise': threshold, 'amount_paise': amount_paise,
            'source': source, 'label': label}


def required_signatures(case):
    return int((case.approval_policy or {}).get('required_signatures', 1))


def fingerprint(case):
    """SHA-256 over what an authorisation covers. The instrument version is left out on purpose: the workflow itself
    increments it when a decision or letter is recorded."""
    instrument = case.release.instrument
    basis = {
        'instrument': {'id': instrument.pk, 'reference': instrument.reference, 'amount_paise': instrument.amount_paise,
                       'maturity_date': instrument.maturity_date.isoformat(), 'mode': instrument.mode},
        'documents': sorted([d.pk, d.kind, d.sha256] for d in instrument.documents.exclude(kind=Document.Kind.RELEASE_EVIDENCE)),
        'clearances': sorted([t.unit, t.status, t.decided_by_id, t.evidence_ref, t.evidence.sha256 if t.evidence_id else None]
                             for t in case.clearances.select_related('evidence')),
        'penalties': sorted([p.pk, p.kind, p.amount_paise, p.status] for p in case.penalties.all()),
        'penalty_review_complete': case.penalty_review_complete,
        'rule_sha256': case.rule_sha256, 'path': case.path, 'declarations': case.declarations,
    }
    return hashlib.sha256(json.dumps(basis, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def basis_matches(case):
    """None when the case was authorised before fingerprints existed (nothing to compare)."""
    if not case.basis_fingerprint:
        return None
    return fingerprint(case) == case.basis_fingerprint


def must_use_different_completer():
    return bool(getattr(settings, 'RELEASE_REQUIRE_DIFFERENT_COMPLETER', False))
