# Local prerequisite evaluator verification

Date: 24 October 2026. Branch `s/S5-prerequisite-evaluator`, based on `7e05644`.
Scope: pure evaluator, synthetic comparison runner, tests and local documentation.

| Executed check | Actual result |
|---|---|
| Pre-change full baseline | 304 passed in 34.334 s |
| New focused tests | 25 passed in 0.273 s |
| Labeled S5 scenarios | 40/40 expected outcomes and unconditional invariants match |
| Final full suite | 329 passed in 62.640 s |
| Original portal separately | 159 passed in 60.117 s |
| Frozen S2 dataset | 76/76 passed |
| S3 fixture validator | 19 passed, seven calculations, zero queries |
| S4 CSV / KPI datasets | 7/7 and 10/10 passed |
| System / schema checks | No issues, no migration drift; existing obligations 0001 and portal 0001--0004 applied |
| Preservation | No edits to prior application, S1–S4 code/tests/datasets, configuration or requirements |

The first 38/40 result exposed request-actor setup mistakes in S5-29/S5-30; their
inputs were corrected to institution requesters. Original expected labels and
assertions were verified byte-independent against preparation commit `7e05644`
and are pinned by canonical SHA-256 in the new tests. No expectation was rewritten
to accept the evaluator's output.

The broader focused run initially failed on unknown-state classification, absent
successful-assessment provenance, generic penalty clause and missing issued-letter
kind. The evaluator was corrected; all focused tests passed afterwards, including
contradictory monitoring, freshness, reuse/replay and privacy boundary checks.

Core evaluation performs no I/O or mutation and never invokes Django/ORM/services.
The standalone test confirms this import boundary; test cases additionally forbid
queries. Existing regression suites use their normal isolated test databases and
temporary synthetic files. No application data migration, seed or release action
was run. Logs remain under ignored `data/s5-evaluator-*.log`.

No real source/auth/role/clearance/PDF/bank/public integration, API status, rollback
or concurrency behavior was tested by this pure slice. Existing portal tests cover
only their legacy workflows. Synthetic parse/review facts and case projections
must not be presented as observed bank actions or a release already completed.
No production policy, real-data accuracy or time-saving claim is supported.
