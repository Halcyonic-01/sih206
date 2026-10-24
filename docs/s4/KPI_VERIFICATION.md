# Local KPI calculation verification

Date: 24 October 2026. Branch `s/S4-kpi-calculations`, starting from preserved
CSV checkpoint `ff91fc1`. Existing Python 3.12 environment on Windows.

- Pre-change full baseline: **282 tests passed in 34.109 s**.
- New focused KPI suite: **22 tests passed in 0.243 s**.
- Labeled synthetic KPI datasets: **10/10 passed**, including two expected
  controlled input rejections. No independent reviewer adjudication is claimed.
- The first focused run exposed two gaps in the new validation: cyclic renewal
  links and conflicting institution IDs across renewal/successor snapshots.
  Both now fail with `KpiInputError`; tests passed after the fixes.
- Standalone subprocess verifies the module/evaluator work without importing
  Django or database code. `SimpleTestCase` also forbids database access.
- Previous CSV dataset: **7/7 passed**. Frozen S2 dataset: **76/76 passed**.
  S3 fixtures: **19 passed**, seven calculations, zero queries.
- Django checks passed, no migration drift; existing obligations 0001 and portal
  0001--0004 remain applied. No application/source schema was changed.

- Final full regression: **304 tests passed in 63.199 s**.
- Original portal regression, run separately: **159 passed in 60.595 s**.
- Preservation diff: all previous application, model/migration, S1/S2/S3 and CSV
  code/tests/labels unchanged. Only a documentation link was added to S4's index.
- Documentation links and Git whitespace checks passed.

No real audit-event adapter, endpoint, chart, writes, migrations or new dependency
was added. No authentication, authorization, bank integration or time-saving
study is implemented/tested by this slice. Current process durations include
waiting/correction time; they are not officer handling time. Historical completion
cohorts and observed-subset rates are explicitly labelled in the specification.

The original application, S1–S3 preparation and S4 CSV source/tests/labels remain
unchanged. Local synthetic fixtures and computations cannot establish that a real
source is complete, that all eligible instruments were supplied or that a bank
confirmation is authentic. These remain future integration/validation concerns.

Private test logs are under ignored `data/s4-kpi-*.log`. Existing historical
verification reports remain dated records of their earlier checkpoints.
