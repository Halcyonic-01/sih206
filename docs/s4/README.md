# S4: institution CSV preparation only

The later [KPI definitions and pure calculation slice](KPI_GUIDE.md) is documented
separately. This page continues to describe the preserved CSV slice.

Start with the [CSV specification and acceptance cases](CSV_SPEC.md). The code is
[the pure validator](../../obligations/csv_validation.py); the fictional inputs
and literal labels are in [evaluation/s4](../../evaluation/s4/README.md).

This slice validates in-memory bytes and explicit identity snapshots. It does
not create a database row, import service, migration, API, upload form, preview
screen, report or KPI page. S1–S3 and the existing browser application remain
unchanged. Everything is local; nothing is pushed.

## Run from the repository root

Use the project's existing Python 3.12 environment and requirements. No new
packages or separate frontend setup are required.

```powershell
.\.venv\Scripts\python.exe -m evaluation.s4.run
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_csv_validation
```

Expected: seven labelled scenarios pass with `failed: 0`; 23 focused tests pass.
The evaluation command prints comparison results, **not** a list of institutions
imported into the database. It never writes a report or row. Its exit code is 1
when labels mismatch, otherwise 0. Django settings are not required by that
command; Django's pinned core email validator must be installed.

To inspect one fictional file without starting a server:

```python
from pathlib import Path
from obligations.csv_validation import validate_institution_csv

result = validate_institution_csv(
    Path("evaluation/s4/valid.csv").read_bytes(),
    existing_identities=(),  # Explicitly empty synthetic context, not a DB query.
)
assert result["status"] == "VALID"
assert result["valid_count"] == 3
assert result["valid_rows"][0]["values"]["aicte_id"] == "000123"
```

Run that snippet from the repository root in Python. The outer `Path.read_bytes`
belongs to the example caller; the validator itself accepts no path or handle.

For error cases, inspect `evaluation/s4/invalid-fields.csv` and `cases.json`.
The mixed case has seven rejected rows plus one candidate. Overall status stays
INVALID; no automatic partial import or update is authorized. Existing identities
must be supplied as typed `ExistingIdentity` snapshots; legacy institutions may
have a null AICTE ID but still block their known institution code.

## Regression gate

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test portal.tests
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe docs/s3/validate_fixtures.py
.\.venv\Scripts\python.exe -m evaluation.s2.run --output data\s4-s2-regression-evaluation.json
```

The existing upload/packaging tests require normal Windows temporary-directory
access. No application permission or test should be disabled to work around a
sandbox's filesystem restriction. See [actual verification](VERIFICATION.md).

Before any future import commit, agree the real source schema/identifier mapping,
scope and roles, entity audit/version handling, atomic conflict behavior, replay
policy and preview freshness with K1/S2. Concurrent database uniqueness must be
rechecked at commit time. These future pieces are not implemented here. XLSX
reports, KPIs, Yash's instrument adapters and Kushagra's platform remain outside
this slice.
