# Local S3 preparation verification

Date: 24 October 2026. Runtime: project `.venv`, Python 3.12.14, Windows.
Branch: `s/S3-screen-spec`, based on preserved S2 checkpoint `3888ec4`.
This checkpoint adds specification, synthetic fixtures, their validator and tests;
it implements no application screen, HTTP endpoint, database schema or shared shell.

| Check actually run | Result |
|---|---|
| Baseline `manage.py test`, before validator/test additions | 225 passed in 55.680 s |
| `python docs/s3/validate_fixtures.py` | 19 scenarios passed; seven calculation cases, including one expected rejection; zero DB queries |
| `manage.py test obligations.tests.test_s3_fixtures` | 10 passed in 0.049 s, with corrupted-copy rejection checks |
| Final `manage.py test` | 235 passed in 60.482 s |
| Final `manage.py test portal.tests` | Original 159 passed in 58.494 s |
| `manage.py check` | No issues |
| `manage.py makemigrations --check --dry-run` | No changes detected |
| `manage.py showmigrations` | Existing migrations applied, including obligations 0001 and portal 0001--0004 |
| Existing S1/S2 application/test and frozen dataset preservation | No tracked edits outside the new S3 preparation files and new validator test |

An initial restricted-sandbox baseline failed (100 failures, 25 errors) because
temporary PDF test-file access raised `PermissionError`. The baseline was rerun
with normal temporary-file access and passed before changes. Final regression
runs used that access too. No application permissions or tests were weakened.
Private logs remain under ignored `data/s3-*-tests.log`.

The validator checks exact numbers, draft provenance/fingerprint, proof deadline,
finding codes, scenario references, scope consistency, denied-state data absence,
unknown versus unavailable amounts, expected rejection and stale-preview absence.
It is not a complete JSON schema or an independent regulatory accuracy evaluation.
It compares presentation examples with the existing draft S2 engine. Synthetic
labels have not received independent policy-owner adjudication.

S3 HTTP authorization, browser rendering, keyboard/mobile behavior, live response
races, PDF links, real adapter integration and shared frontend builds remain
untested because those S3 implementations do not exist in this checkout. The
passing original portal tests do not establish that S3 is complete.

Read [contract gaps](CONTRACT_REVIEW.md) before implementation. No network fetch,
push, merge or shared-contract change was performed for this checkpoint. A local
commit saves the reviewed preparation; K1/K2/Y1 remote merge status was not checked.
