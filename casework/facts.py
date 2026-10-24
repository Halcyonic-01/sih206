"""Fail-closed boundary for release decisions' trusted factual context.

The release service owns orchestration, immutable case state and decisions.  A
separate authorized integration must supply the canonical Affidavit-6 revision,
typed-document parse results, page references and path-specific requirements.
This module deliberately accepts no fixtures, browser values or inferred bank
facts.  Tests opt in with an explicit settings override.
"""
from copy import deepcopy

from django.conf import settings

from obligations.release_prerequisites import SECTIONS, TOP
from obligations.services import DependencyUnavailable


CONTRACT_VERSION = 'release-facts-v1'


def assemble(*, actor, instrument, obligation, path, declarations):
    """Return an isolated, complete facts snapshot or fail closed.

    The copied result prevents a provider retaining a mutable object that the
    release service subsequently enriches with actor/case state.  The exact
    shape check keeps malformed integrations from being reinterpreted as a
    partial successful assessment.
    """
    provider = getattr(settings, 'SAKSHAM_RELEASE_FACTS', None)
    if not callable(provider):
        raise DependencyUnavailable('Trusted document/questionnaire adapter unavailable.')
    result = deepcopy(provider(actor=actor, instrument=instrument, obligation=obligation,
                               path=path, declarations=deepcopy(declarations)))
    if type(result) is not dict or set(result) != TOP or any(type(result.get(section)) is not dict for section in SECTIONS):
        raise DependencyUnavailable('Invalid trusted release context.')
    return result
