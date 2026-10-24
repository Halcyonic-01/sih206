# Y1: deposit and document storage fields

Y1 extends the existing portal schema through `portal.0005_record_fields`, which
depends on `obligations.0001_initial` and `portal.0004_release_workflow`.
It adds storage and validation, not new screens, APIs, rule calculations, PDF
parsing, bank confirmation or RTGS processing workflows.

## Contract

- `Instrument.obligation`: optional protected FK to `DepositObligation`, reverse
  name `instruments`. Multiple holdings may cover the same obligation. Model
  validation rejects links to another institution. Call `full_clean()` before
  saving supplied values; direct/bulk writes do not enforce this cross-table rule.
- `mode`: `FDR`, `RTGS`, `RPGF`; existing records are FDRs.
- `ifsc`, `branch`, `holder_names`, `utr`: optional strings. An IFSC, if supplied,
  must have the uppercase 11-character format. Format does not establish issuer
  identity. Mode-specific submission rules and form/API exposure belong to Y3.
- `lien_marked`: nullable boolean; null means unknown, not no lien.
- `verification_level`: `DECLARED`, `REVIEWED`, `CONFIRMED`, `DISCREPANCY`.
  All existing records default to DECLARED, including accepted records. Y1 does
  not promote any record or create evidence. Evidence-backed changes belong to Y6.
- `Document.page_count`: optional positive integer. Existing values stay unknown;
  Y2 will parse uploads and validate observation bounds.
- Document kinds include payment/RPGF proof, affidavits 3/6, LoA/EoA, bank
  certificate, request letter, student clearance, external NOC, issued NOC,
  sanction order and the existing FDR/release evidence. These are categories, not
  a regulatory checklist or permission to issue a letter.

Database constraints reject invalid deposit modes, verification choices and
nonpositive page counts. Existing money, dates, lineage, release and observation
constraints remain. New workflow audit snapshots include the added instrument
fields; old snapshots are not rewritten. Existing forms still implement the FDR
workflow and expose none of the new fields yet.

## Verification

Run `manage.py check`, `manage.py makemigrations --check --dry-run`,
`manage.py test portal.tests` and `manage.py test` using the project venv.
The Y1 migration test upgrades synthetic pre-Y1 records and compares all old
instrument, document and audit columns, retaining lineage and unknown defaults.
Apply with `manage.py migrate` after backing up any needed local database and
documents together. This migration does not parse or rewrite stored PDFs.
