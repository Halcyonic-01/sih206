# Semifinal evidence and evaluation upgrade

Priorities 2–4 of the two-day plan, implemented locally. This is a synthetic hackathon build, not a statement of bank authenticity or approved regulatory policy.

## What changed

### Clearance evidence

Each assigned clearance unit uploads and selects its own supporting PDF on its case card. The existing bounded PDF validator checks it. Uploading does not clear a task. A human separately records Cleared, Objection or Hold with a reason and file reference.

The release page shows the linked evidence, reviewer and decision time. The assigned unit, officer and authority may view the PDF. Other units, institutions and unassigned readers cannot download it. Existing case scope checks still run first. PDFs use the existing local PDF.js viewer and the session/CSRF API client, with a protected download fallback and an access-log entry.

Storage: `obligations.ClearanceEvidence` holds the bounded PDF bytes, hash, size, page count, uploader and timestamp. Its model rejects ordinary updates/deletes. Evidence selection belongs to one task (therefore one case/unit). Database transactions cover blob creation, case version and audit. This deliberately follows the existing issued-letter binary storage pattern; it is not a new object-storage service. It is application-level append-only storage, not tamper-proof database infrastructure. The hash is checked again when viewing and deciding.

Migration: `obligations/0008_clearance_evidence`. Existing migrations were not edited. Historical references were not converted into invented evidence or timestamps.

Legacy behavior: pending reference-only clearances are labelled and block a new authorization until their assigned unit re-attests the same status with a PDF. The previous decision remains in the audit history. A linked decision cannot be overwritten; completed cases are not rewritten. Evidence PDFs remain private after completion.

New endpoints (relative to `/api/`, no trailing slash):

| Endpoint | Behavior |
|---|---|
| GET `releases/{case}/clearances/{unit}/evidence` | Protected metadata list and current case version. |
| POST same | Multipart `version`, `document`; returns 201 with evidence metadata and incremented version. |
| GET `releases/{case}/clearances/{unit}/evidence/{id}` | Logged, no-store PDF response; scope and hash verified. |
| POST `releases/{case}/clearances/{unit}` | Existing decision API now also requires positive integer `evidence_id`. |

New decisions require a valid PDF link even when the reference-validation adapter is replaced. Invalid input is 400, unauthorized scope is 403/404, stale writes are 409, and storage/access-log failures return a safe 503. No PDF bytes are released if access logging fails. Upload count is capped at ten per task, in addition to the existing size/parser limits.

### Extraction evaluation

`fixtures/ai-evaluation/manifest.json` defines twelve invented CC0 test PDFs with hashes, expected values, expected pages, mismatch labels and fixed tuning/held-out membership. Four are clean text samples, three scans, two intentional declared-value mismatches, two missing/conflicting-value samples and one unreadable scan. The clean sample T04 also includes untrusted instruction-like text. All samples are marked synthetic.

The generator is `scripts/build_extraction_dataset.py`. A second human has not independently signed off these labels. Inspect all PDFs and the manifest before presenting the set as independently verified. The held-out designation is fixed but this small corpus is not a representative regulatory benchmark.

`evaluate_extraction` preserves the original single-scan smoke interface and adds dataset validation, subset selection and JSON reports. It measures normalized field values and pages, wrong/missing/invented values, mismatch TP/FP/FN, per-field precision/recall and end-to-end timings. Undefined metrics are JSON null, not 100%. Failures stay in denominators. Successful all-null abstention is distinct from an unavailable service response.

The offline text baseline uses PDF text and the existing local parser; it cannot read image-only PDFs and is not labelled OCR or AI. Real OCR uses the existing OCR service, and live AI uses the existing configured provider/service with AI run logging and its ordinary quota. The evaluator does not bypass rate limits or cache a fake success.

Two verified extraction defects were fixed: a non-null value without a supporting page is rejected; local OCR/other operation logs no longer consume DOCUMENT_EXTRACTION's hourly quota. Unsupported extraction remains advisory and never changes deposit status, verification, penalties or release decisions.

### Rehearsal and installation

`config.rehearsal_settings` always uses a separate SQLite database/media tree, local-memory email, and AI/OCR off. `config.evaluation_settings` uses a separate evaluation database and enables the existing configured engines. Neither profile changes `.env` or the normal app database.

`scripts/prepare_semifinal.py` copies synthetic fixtures and uses existing migration and seed commands. It preserves seeded accounts/data; each invocation adds a fresh release rehearsal holding through the normal services. The latest scenario ID is written privately to `data/semifinal/data/release-scenario.json`. Generated passwords are private files in that same directory.

`scripts/check_semifinal_install.py` makes a new source-only candidate folder under ignored `data/semifinal-installs`, excluding secrets, credentials, normal data, planning, builds and dependencies. It runs the existing installation/smoke launcher there and records copied source hashes. This verifies local uncommitted source; `scripts/review_check.py` still uses committed HEAD for its own fresh-install step.

## Run the safe local demonstration

From the repository root after the standard Python 3.12 / Node 22 dependency setup:

```powershell
Push-Location frontend
npm ci
npm run build
Pop-Location
.\.venv\Scripts\python.exe scripts\prepare_semifinal.py
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8011 --settings=config.rehearsal_settings --noreload
```

Open `http://127.0.0.1:8011/login`. Read passwords locally from `data/semifinal/data/demo-credentials.txt`, `authority-credentials.txt`, and `staff-credentials.txt`. Never commit or share those files publicly. The normal port-8010 app/database has not been migrated by these commands. Back it up and explicitly select the intended database before applying any migration there; never accidentally run the default migrate command against a shared DATABASE_URL.

Demo line: “Each clearance now points to a protected supporting PDF. The reviewer records a separate decision, and the authority reviews the case independently.”

1. As `institution_a`, open the reference in `release-scenario.json` and request release: Term complete, a synthetic reason, six Yes declarations, readable checklist, submit.
2. Note the new case number. As each of `clearance_pgrc`, `clearance_vigilance`, `clearance_grants`, open Clearance work and that case's card.
3. Upload `fixtures/release-evidence.pdf`, wait for the card to reload, select the uploaded PDF, click View supporting PDF, inspect it, enter your reason and unit-specific reference, then click cleared.
4. As `officer`, open that release case. Inspect clearances and PDFs, enter a review reason and record officer checklist and penalty review complete.
5. As `authority`, independently inspect all three PDF links, enter a reason and record authority authorization. Issue the unsigned letter and download it.
6. Enter completion notes, attach a new synthetic completion PDF and record evidence-backed completion. Confirm Completed and monitoring ended. The portal does not execute bank payments.

## Reproduce evaluation

Run corpus validation without provider calls:

```powershell
.\.venv\Scripts\python.exe manage.py evaluate_extraction --manifest fixtures/ai-evaluation/manifest.json --validate-only --settings=config.evaluation_settings
```

On first use, prepare the separate evaluation database:

```powershell
.\.venv\Scripts\python.exe manage.py migrate --settings=config.evaluation_settings
.\.venv\Scripts\python.exe manage.py seed_demo --generate-password --settings=config.evaluation_settings
.\.venv\Scripts\python.exe manage.py seed_extraction_evaluation --confirm-disposable --settings=config.evaluation_settings
```

Run one engine at a time and save a new report filename for each measured run:

```powershell
.\.venv\Scripts\python.exe manage.py evaluate_extraction --manifest fixtures/ai-evaluation/manifest.json --engine text --output data/semifinal-text-rerun.json --settings=config.evaluation_settings
.\.venv\Scripts\python.exe manage.py evaluate_extraction --manifest fixtures/ai-evaluation/manifest.json --engine ocr --output data/semifinal-ocr-rerun.json --settings=config.evaluation_settings
# Only with explicit approval to transfer these synthetic PDFs externally:
.\.venv\Scripts\python.exe manage.py evaluate_extraction --manifest fixtures/ai-evaluation/manifest.json --engine ai --allow-external --output data/semifinal-ai-rerun.json --settings=config.evaluation_settings
```

Use `--subset heldout` for the fixed held-out subset. Live runs consume API quota and the app's ten-attempt hourly limit. Do not reset logs, create accounts or weaken limits to make results look better. The measured run hit the limit on the final two samples; their provider accuracy remains unmeasured. Tesseract was unavailable in this environment, so all local OCR attempts failed safely; install/configure the existing optional OCR tool before claiming OCR accuracy.

## Reproduce browser and recovery checks

With the disposable server already running, create a new release scenario before repeating the release test:

```powershell
.\.venv\Scripts\python.exe manage.py seed_semifinal_release --settings=config.rehearsal_settings
$env:SEMIFINAL_DISPOSABLE='1'
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:8011'
$env:DEMO_CREDENTIALS_FILE=(Resolve-Path data/semifinal/data/demo-credentials.txt).Path
# Set PLAYWRIGHT_BROWSERS_PATH if your installed browser is in a non-default cache.
Push-Location frontend
npx playwright test
Pop-Location
```

The new browser tests require the explicit disposable flag and port; they fail closed rather than mutate a normal demo database. The release test blocks external requests while permitting loopback traffic. This verifies external-network-independent operation in Chromium, not a physical Wi-Fi disconnect or every possible browser.

Fallback: keep the built frontend, installed dependencies, synthetic PDFs and the private disposable data directory on the target laptop. Stop the rehearsal server before copying its database/media/credential directory to a private backup. Preserve its audit key configuration; never copy `.env` into Git. Restart the same profile and verify health, saved decisions, PDF views and the audit chain. A blank-data fresh install is a separate check, not a restore of existing decisions. Use recorded synthetic AI results labelled as recordings if the provider is unavailable; the manual process remains the live fallback.

## Remaining human checks and boundaries

- Independently review and sign off the synthetic ground truth.
- Verify the final candidate on the physical semifinal laptop and chosen browser, including an actual disconnected-network rehearsal and PDF download behavior.
- Real SMTP, a shared PostgreSQL deployment, official policy approval, authentic bank confirmation and digitally signed letters are not verified by these local checks.
- Keep this work local until the team reviews the new evidence API, migration and legacy pending-case policy. No push or merge was performed.

See the companion results document for actual measured counts, commands, failures and limitations; do not infer a passing release from code being present.
