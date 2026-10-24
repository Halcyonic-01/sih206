# S6 validator and contract review verification

Local checkpoint reviewed: `07163b2` (S6 documentation/fixtures following S1–S5).
This follow-up adds only an offline preparation validator, its tests, contract
review and documentation. The original 53 fixtures and all S1–S5 existing files
remain unchanged. No fetch, push, API, frontend, migration or application-data
write is part of this work. Test databases and temporary files are isolated.

## Actual results — 24 October 2026

| Command / check | Result |
|---|---|
| Baseline `manage.py test` before edits | 329 passed, 55.870s |
| `python docs/s6/validate_fixtures.py` | 53 fixtures passed; 48 private, five public, 33 S5 comparisons; zero queries |
| `manage.py test obligations.tests.test_s6_fixtures` | 18 passed, 3.083s |
| Final `manage.py test` | 347 passed, 43.666s |
| Separate `manage.py test portal.tests` | 159 passed, 38.531s |
| `manage.py check` | No issues |
| `manage.py makemigrations --check --dry-run` | No changes detected |
| Migration inspection | Existing obligations 0001 and portal 0001–0004 applied; none added/applied |
| Existing S2 runner | 76/76 passed |
| Existing S3 validator | 19 scenarios passed; seven calculations, one expected rejection, zero queries |
| Existing S4 CSV / KPI runners | 7/7 and 10/10 passed |
| Existing S5 runner | 40/40 passed; prior expected-label hash unchanged |

The first focused run found a bug in one new test: an intentionally emptied task
list was reused for the subsequent invalid-date check. Resetting the test input
before that check fixed the error; no source fixture or application logic was
changed to make a failing assertion pass. The subsequent focused and full runs
above passed. Counts overlap and are not independent new product test counts.
Normal Windows temporary-file permissions were used for PDF/packaging and CLI
subprocess tests. Local logs are ignored under `data/s6-validator-*.log`.

## What the new tests establish

The 18 tests use deliberately corrupted in-memory fixture copies to check:

- Required IDs/screens/states/labels and lineage/operation cannot disappear,
  duplicate, change meaning or replace S5 outcomes/reasons silently.
- Supplied actor/scope changes, unexpected permission grants and private payloads
  in denied/loading/session/error/race states are rejected as fixture inconsistencies.
- Completion/approval/rejection projections cannot replace pre-action saved status,
  monitoring or version. JSON true cannot substitute for integer version 1.
- Unknown penalty review, unavailable template/page count, invalid upload,
  invalidated preview and legacy monitoring cannot become successful facts.
- Queue scope, task status/dates and empty/error payloads retain their v1 meaning.
- Public field expansion, private metadata, changed revocation, failed-service
  success and wrong lineage are rejected. Public record fields are exact synthetic
  v1 labels, not values fetched from an application.
- Malformed shapes/custom objects/cycles, floats/unsafe integers, duplicate JSON
  keys, invalid UTF-8, NaN, unreadable and over-1-MiB files fail in controlled ways.
- The CLI succeeds from another working directory, exits nonzero on invalid input,
  redacts raw I/O exception details and still checks data with Python `-O`.
- Inputs, S6 fixture bytes and S5 source bytes remain unchanged. Query guards are
  installed on configured connections and restored after failure; SimpleTestCase
  also prohibits actual database access.

This validator is intentionally specific to the frozen v1 presentation examples.
It does not regenerate labels from implementation output. Changes to scenario
meaning require reviewed labels, validator expectations and tests together.
Natural-language checks remain a human review responsibility; the gate cannot
prove their meaning merely by checking a nonempty list.

## Contract review conclusions

[CONTRACT_REVIEW.md](CONTRACT_REVIEW.md) maps four screens to actual source,
missing field/permission/version contracts, owners and unresolved S5-D01–D09.
The screen spec now explicitly distinguishes legacy instrument versions from
illustrative S5 case revisions and conservative denied fixtures from live
read-versus-action authorization semantics. No shared contract was declared agreed.

Blockers remain: canonical questionnaire; scoped holding/obligation/document
adapters and viewer metadata; persisted S5 cases/tasks/letters; aggregate freshness
and server actions; K4 unit powers/independence/waivers; settlement semantics; public
publication/token lifecycle; K1/K2 integration and K5 notifications. These are
integration/policy decisions, not missing code to implement opportunistically here.

No API, role enforcement, browser, PDF preview, accessibility, public token lookup,
bank confirmation, legal eligibility, notification or end-to-end S6 success is
claimed. Regression tests establish preservation of the tested existing behavior.
Use [README.md](README.md) for repeatable commands and future acceptance boundaries.
