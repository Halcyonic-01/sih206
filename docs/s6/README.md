# S6 release UI preparation

Later [owned feature components](../owned/README.md) now implement these screens in
isolation. They are not mounted in K2's shell and do not make S6 integration complete.
This folder retains the original preparation corpus and its validator unchanged.

Start with [SCREEN_SPEC.md](SCREEN_SPEC.md), then [fixtures.json](fixtures.json).
See [CONTRACT_REVIEW.md](CONTRACT_REVIEW.md) for screen-to-source gaps and
[VALIDATOR_VERIFICATION.md](VALIDATOR_VERIFICATION.md) for current test results.
[VERIFICATION.md](VERIFICATION.md) retains the original documentation-only record.

This folder contains documentation, synthetic presentation fixtures and an offline
preparation validator. The validator has negative tests in the existing test suite.
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
Run from the repository root:

```powershell
.\.venv\Scripts\python.exe docs/s6/validate_fixtures.py
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_s6_fixtures
```

Expected CLI result: `result: passed`, 53 scenarios, 48 private, five public,
33 S5 comparisons and zero database queries; exit 0. The focused suite has 18 tests.
Use `--fixtures path/to/candidate.json` to check a candidate without modifying
source labels. Contract failures print a controlled diagnostic to stderr and exit 1;
malformed JSON, duplicate keys, missing/unreadable files and oversized files also
fail. Argument syntax errors use argparse's exit 2. Never count a failure as a pass.

The validator checks the fixed v1 scenario IDs/screens/states, explicit synthetic
and draft labels, actor/scope context, S5 lineage/operations/outcomes/reasons,
pre-action saved status/version/monitoring, required prohibited controls, unknown
versus false/zero, error/denial empty payloads and a separate minimal public shape.
It rejects added permission grants and public fields. It uses unchanged local S5
sources and pure functions, blocks queries on every configured Django connection,
and reads no users/documents or application data. It writes no fixtures or database
rows and needs no migrated database. CLI paths work from another working directory;
checks remain active with optimized Python (`-O`).

Presentation-only v1 payloads are deliberately fixed, so changing a scenario's
meaning requires an explicit contract/label review and validator/test update, not
an automatic regeneration of expected results. Reordering scenarios is allowed.
Natural-language prose is checked for presence, not proven semantically correct;
headings on public states are fixed to distinguish revoked, missing and failed.
This is not API, role enforcement, PDF validity, accessibility or browser testing.

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
