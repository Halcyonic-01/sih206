# S4 KPI preparation: run and inspect

Read [definitions, cohorts and unknown-data behavior](KPI_SPEC.md) first. Code:
[obligations/kpis.py](../../obligations/kpis.py). Labeled inputs:
[evaluation/s4/kpis](../../evaluation/s4/kpis/README.md).

This is a pure, explicitly SIMULATED calculation slice. It never reads actual
audit events, changes a record, queries a database or contacts a bank. It does not
create a KPI endpoint, chart, dashboard, report, scheduler or notification. The
existing S1–S3 and CSV preparation remain intact.

From the repository root, with the existing Python 3.12 environment:

```powershell
.\.venv\Scripts\python.exe -m evaluation.s4.kpis.run
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_kpis
```

Expected: 10 labelled cases pass, zero mismatches; 22 focused tests pass. The
evaluation command reads local synthetic JSON, prints comparison counts and exits
0 on success or 1 on mismatch. It writes no file or database row. The calculation
module uses only Python standard-library modules and existing timezone data;
neither Django configuration nor a running server is needed to evaluate fixtures.

For an example result without Django setup:

```python
import json
from evaluation.s4.kpis.run import DATASET, inputs
from obligations.kpis import calculate_kpis

dataset = json.loads(DATASET.read_text(encoding="utf-8"))
case = next(c for c in dataset["cases"] if c["id"] == "mixed-completed-cohort")
result = calculate_kpis(**inputs(case, dataset["context"]))
assert result["submission_to_acceptance"]["sample_count"] == 4
assert result["submission_to_acceptance"]["median_seconds"] == "9000.000000"
assert result["correction_cycles"]["mean_per_accepted_record"] == "0.75"
assert result["confirmed_share"]["percentage_bps"] is None
assert result["confirmed_share"]["known_subset"]["percentage_bps"] == 3333
```

The last two assertions deliberately differ: the complete accepted cohort has
one unknown verification state, while its known subset has one confirmation
among three known states. Showing 33.33% as the entire cohort's result would be
misleading. Likewise, no samples mean unavailable median/p90, not zero time.

For renewal examples, inspect `renewal-ist-deadline-and-unknowns` and
`maturity-day-still-open`. A successor accepted at 18:29:59 UTC on maturity day is
on time by the demo's IST-date definition; 18:30 UTC is the next IST day. The
observation day must finish before its maturity enters the scored denominator.
These are synthetic analytics conventions, not bank settlement or policy proof.

Regression commands:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test portal.tests
.\.venv\Scripts\python.exe manage.py test
.\.venv\Scripts\python.exe -m evaluation.s4.run
.\.venv\Scripts\python.exe docs/s3/validate_fixtures.py
```

Upload/packaging regression tests require normal Windows temporary-file access.
See [actual KPI verification](KPI_VERIFICATION.md). No new dependency was added.

Before a real adapter/API, agree history completeness, scoped populations,
event vocabulary/order, cutoffs, verification state and renewal eligibility with
Yash/Kushagra. This format does not replace the team's audit/API contracts.
Any UI must show samples, unknowns, exclusions, window and cutoff explicitly.
Real-world improvement needs a separate authorized baseline study; these fixtures
provide no evidence of time saved or accuracy gains.
