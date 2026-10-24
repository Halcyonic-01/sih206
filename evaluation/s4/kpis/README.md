# Labeled synthetic KPI event snapshots

All records/events are fictional and SIMULATED. No real applicant data or actual
audit export was used. Labels are author-written and not independently
adjudicated. `cases.json` has ten alternative datasets, not one combined database.

| Scenario | Literal expected behavior |
|---|---|
| empty-known-population | Zero samples; null median, p90, mean and percentages |
| mixed-completed-cohort | Four accepted durations: 1/2/3/4 hours; median 2.5 hours, p90 4 hours; three correction cycles, mean 0.75; overall confirmed share unknown |
| pending-incomplete-outside-and-future | No completed samples; two open submissions, one incomplete history and one ignored future event |
| renewal-ist-deadline-and-unknowns | One on-time among three known eligible matured predecessors; explicit unknown/incomplete exclusions make overall rate unavailable |
| maturity-day-still-open | Same-day maturity not scored before the day ends in IST |
| microseconds-ties-and-observed-zero | 1/2 microsecond durations, half-up 2 microsecond median; real zero corrections and 50.00% confirmed |
| inclusive-window-and-zero-duration | Both completion-window endpoints included; genuine zero elapsed time included |
| reconfirmation-preserves-first-confirmation-time | Current confirmation restored; first-confirmation duration remains two hours |
| cross-institution-record-rejected | Controlled input error; no scope widening |
| complete-history-missing-submission-rejected | Controlled input error; no invented submission timestamp |

During authoring, the outside-window renewal fixture initially used 1 May, but
the UTC end instant touches 1 May in IST. Its maturity was corrected to 2 May to
test the intended outside-window case; the literal expected outcome was retained.
No prior frozen S2/CSV labels or reports were modified.

```powershell
.\.venv\Scripts\python.exe -m evaluation.s4.kpis.run
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_kpis
```

Run from repository root. `inputs()` decodes synthetic JSON into value objects;
it is not an ORM/API adapter. The evaluator compares expected nested fields with
strict value types and fails nonzero on any mismatch. It does not create labels
from the implementation. Its CLI summary does not represent real-world KPI
measurements. A negative test corrupts confirmed counts and verifies detection.

Additional unit tests independently compare 20 distributions against Python
statistics/nearest rank, verify resubmission timing, UTC/IST equivalence, unknown
denominators, snapshot immutability, scope and chronology failures, duplicate or
cyclic lineage, exact durations and standalone operation without Django.

The vocabulary and cohort conventions are local proposals. Do not equate
ACCEPTED with INDEPENDENTLY_CONFIRMED, and do not turn draft renewal links into
accepted-successor snapshots. Complete/scoped inputs are caller facts; this
evaluator proves neither source completeness nor authorization.
