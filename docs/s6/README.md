# S6 release UI preparation

Start with [SCREEN_SPEC.md](SCREEN_SPEC.md), then [fixtures.json](fixtures.json).
See [VERIFICATION.md](VERIFICATION.md) for actual checks and their limits.

This folder contains documentation and synthetic presentation fixtures only.
No React setup, component, frontend route, API, database write, migration, document
generation or token lookup was added. S1–S5 and the existing Django app are preserved.
Full S6 is not implemented. Integration needs the actual S5 backend, K2 shell and
the contracts listed at the end of the screen specification.

## Read the fixtures

There are 53 independent alternatives: 48 authenticated scenarios (13 wizard,
31 case, four clearance-queue) and five public scenarios. They are not a single
user journey or a database to import. They contain fictional metadata only, no
PDFs, working URLs, tokens, passwords or real applicant records.

Each private scenario has `screen`, `state`, illustrative `actor`, `condition`,
`view_data` and literal `expected` presentation assertions. The actor is context,
not an access grant. `prohibited_controls` means a control must not be usable;
all other controls still require server permission. Empty denied/error payloads
must not be populated by an old response or global fixture defaults.

33 private scenarios reference unchanged S5 inputs. Resolve `condition.s5_ref`
in [S5 scenarios](../s5/scenarios.json), deep-copy S5 defaults and recursively merge
that case's input patch. Dictionaries merge; arrays/scalars/null replace. Compare
only the selected example; never merge alternatives. `s5_outcome` describes the
existing pure evaluator, not an HTTP status, persisted decision or live API.
`view_data` deliberately keeps the supplied **pre-action** saved status/monitoring.

Read `case-approve-projection` and `case-complete-projection` first: a successful
simulation still leaves the displayed saved case PENDING or APPROVED respectively.
Read `wizard-template-unavailable` next: the eleven-question template is missing,
so the actual declaration form cannot be built from invented aggregate answers.
Then compare open clearance, unknown penalty, requester conflict and stale cases.

`wizard-review-request` is a presentation contract, not an additional evaluator
measurement. It specifies that initial submission does not require completed
parallel clearances/penalty review; a future server must still evaluate REQUEST's
scope, evidence, basis, holds and version. Other presentation-only cases describe
network, viewer, focus, role, legacy and queue states without pretending to execute them.

The five public examples are a separate collection with a conservative record
allowlist. They must not import private defaults/actors or the evaluator dictionary.
The revoked example has conceptual S5-36 lineage only; its fictional serial/date/
institution are new presentation labels, not an actual lookup result. Publication
of amount remains unresolved; these examples omit it. No sample mints a token.

## Local checks (PowerShell, repository root)

No dependency installation is needed beyond the existing project environment.
This in-memory preparation check executes the existing S5 evaluator, validates
literal expected labels, retained pre-action status and minimal public data. It
does not add a runtime validator, seed records or test a UI:

```powershell
@'
import json
from collections import Counter
from pathlib import Path
from evaluation.s5.run import context, merge
from obligations.release_prerequisites import evaluate_prerequisites

d = json.loads(Path('docs/s6/fixtures.json').read_text(encoding='utf-8'))
s5 = json.loads(Path('docs/s5/scenarios.json').read_text(encoding='utf-8'))
source = {s['id']: s for s in s5['scenarios']}
rule, when = context(s5)
private, public = d['private_scenarios'], d['public_scenarios']
all_cases = private + public
assert d['fixture_format'] == 's6-release-ui-spec-v1'
assert d['artifact_status'] == 'SPECIFICATION_ONLY_NO_FRONTEND'
assert d['simulation_label'] == 'SIMULATED'
assert d['data_classification'] == 'SYNTHETIC'
assert d['rule_status'] == 'DRAFT_DEMO_NOT_APPROVED'
assert len(private) == 48 and len(public) == 5
assert len({s['id'] for s in all_cases}) == 53
assert Counter(s['screen'] for s in private) == {
    'wizard': 13, 'case': 31, 'clearance_queue': 4}
linked = 0
for s in private:
    assert s['expected']['checks'] and s['expected']['heading']
    assert s['expected']['prohibited_controls']
    if s['state'] in {'loading', 'service_unavailable', 'session_expired',
                      'late_response', 'access_denied', 'conflict'}:
        assert s['view_data'] == {}
    ref = s['condition'].get('s5_ref')
    if not ref:
        continue
    linked += 1
    c = source[ref]
    assert s['condition']['operation'] == c['operation']
    snap = merge(s5['defaults'], c['input_patch'])
    assert s['actor'] == snap['actor']
    result = evaluate_prerequisites(snap, operation=c['operation'], rules=rule,
                                    as_of=when, simulation_label='SIMULATED')
    assert result['outcome'] == s['expected']['s5_outcome']
    assert result['reason_codes'] == s['expected']['s5_reason_codes']
    assert result['projection_only'] and not result['effects_applied']
    if result['outcome'] == 'DENIED':
        assert s['view_data'] == {}
    else:
        v = s['view_data']
        assert v['persisted_case_status'] == snap['case']['status']
        assert v['persisted_monitoring_active'] is snap['monitoring_active']
        assert v['persisted_version'] == snap['case']['version']
        assert v['path'] == snap['case']['path']
        assert v['mode'] == snap['case']['mode']
assert linked == 33
allow = {'serial', 'issue_date', 'institution_name', 'kind', 'status'}
assert set(d['public_record_allowlist']) == allow
for s in public:
    assert set(s) == {'id','screen','state','view_data','expected','s5_lineage_ref'}
    assert s['screen'] == 'public_verify'
    assert set(s['view_data']) <= allow
    if s['state'] in {'ISSUED', 'REVOKED'}:
        assert set(s['view_data']) == allow
        assert s['view_data']['status'] == s['state']
        assert s['view_data']['serial'].startswith('SYNTH-')
    else:
        assert s['view_data'] == {}
    if s['s5_lineage_ref']:
        assert source[s['s5_lineage_ref']]['expected']['outcome'] == 'PUBLIC_REVOKED_RECORD_ONLY'
print('PASS: 53 fixtures; 33 S5 comparisons; pre-action state retained; public allowlist checked')
'@ | .\.venv\Scripts\python.exe -
```

Preserved checks, all read-only except isolated regression test databases/files:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test portal.tests
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe -m evaluation.s2.run --output data/s6-s2-check.json
.\.venv\Scripts\python.exe docs/s3/validate_fixtures.py
.\.venv\Scripts\python.exe -m evaluation.s4.run
.\.venv\Scripts\python.exe -m evaluation.s4.kpis.run
.\.venv\Scripts\python.exe -m evaluation.s5.run
```

Windows PDF/packaging tests require normal temporary-directory access. Inspect
the final `OK` and exit code, not just the number of discovered tests. Do not run
migrations, seeds, uploads or application writes to read these specifications.

## Future implementation acceptance

Only after separate authorization and agreed dependencies: mount in K2's shell,
consume scoped server status/actions, then test wizard submission → parallel human
clearances/penalty review → independent authority decision → issued letter → separate
evidence-backed completion → minimal public issued/revoked lookup. Test allowed,
denied, invalid, stale, missing evidence, failed service, duplicate click, response
race, keyboard and mobile states. Confirm approval alone leaves monitoring active.
No sample here claims that integration, legal eligibility or bank settlement works.
