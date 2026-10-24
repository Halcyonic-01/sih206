# S4 CSV slice verification

Local branch `s/S4-csv-validation`, based on preserved checkpoint `cb7bee9`.
Date: 24 October 2026. Runtime: existing project Python 3.12 environment on Windows.

## Checks actually performed

- Before changes: full baseline **259 passed in 35.197 s**.
- Focused pure-validator suite: **23 passed in 0.563 s**.
- Synthetic labelled evaluation: **7/7 scenarios passed**, zero mismatches.
- Standalone subprocess: validator works without configuring Django, importing
  `django.db`/institution models, reading a database or starting a server.
- Frozen S2 evaluation: **76/76 passed**; original labels/reports unchanged.
- S3 validator: **19 scenarios passed**, seven calculations including one expected
  rejection, zero database queries.
- Django system check: no issues. Migration drift check: no changes detected.
  Existing obligations 0001 and portal 0001--0004 remain applied.

- Final full regression: **282 passed in 61.820 s**.
- Original portal, run separately: **159 passed in 59.010 s**.
- Preservation diff against `cb7bee9`: no edits to any existing S1/S2 code/tests,
  S3 preparation, portal/configuration, migrations or frozen evaluation files.
- Local documentation links and Git whitespace checks passed.

## What these checks mean

Valid/invalid files, fields, duplicates, existing-context conflicts, explicit
limits, deterministic error output and no-query operation are tested. Actual
upload handling, authentication, tenant authorization, atomic writes, stale
previews, audit, concurrent import races, reports and browser integration are not
implemented or claimed to pass. No database migration, seeded institution,
permission decision, external integration or real AICTE record was added.

The validator uses the existing Django core email validator but no application
models or ORM. It performs no file/network I/O, logs no submitted values and
persists nothing. The evaluation caller reads fictional fixture files and prints
comparison results. Labels are author-written, not independently reviewed.

No new dependency, frontend setup, API, background job, notification or product
workflow was created. Private test logs remain in ignored `data/s4-*-tests.log`.
The source schema, identity normalization, importer roles and commit policy still
need team agreement before persistence; this is deliberately a validation slice.
