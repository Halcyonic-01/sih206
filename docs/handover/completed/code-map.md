# Code map: where to look before changing anything

Paths in tables are relative to the project root. Start with a feature's route → view → form/permissions → service → model → template → test. Most consequential behavior belongs in services, not a button handler or template.

## 1. One request in slow motion

Example: an institution submits a draft.

1. The detail template displays a POST form with CSRF and the current hidden version.
2. Django middleware authenticates the session and checks CSRF.
3. portal/urls.py routes the submission to instrument_submit.
4. The view checks institution role and fetches from scoped_instruments, so a forged ID cannot expand ownership.
5. SubmitForm validates the version input.
6. services.submit rechecks the actual record/state, FDR document presence and any predecessor constraints.
7. The service atomically increments the optimistic version, changes state and records an audit snapshot.
8. Success redirects to detail. A known state/version conflict returns 409. A known operational exception raised by the view returns generic 503 after service rollback.
9. The GET detail page displays the committed state, findings, documents and history; it does not itself approve anything.

Do not bypass the service from a future API, background task or admin action. A UI-hidden button is not authorization.

## 2. Files and responsibilities

| File / directory | Responsibility and likely reason to open it |
|---|---|
| manage.py | Django command entry point, not business logic |
| config/settings.py | Runtime config, installed middleware/apps, SQLite/files, demo bounds |
| config/urls.py | Login/logout and portal route inclusion; no exposed admin route |
| portal/models.py | Schema, constraints, model lineage/evidence validation and derived lifecycle properties |
| portal/forms.py | Submitted field types, amount/date checks, upload validation and decision reasons |
| portal/permissions.py | Session role, profile owner, scoped querysets and role gates |
| portal/services.py | Draft/submission/review/observation/renewal transactions, versions and snapshots |
| portal/releases.py | Request/authority decision/completion, evidence storage, conflicts with renewal |
| portal/uploads.py | Bounded envelope checks: extension, MIME, size, header, trailer |
| portal/validation.py | Two current metadata checks, technical-v2 version and serializable findings |
| portal/deadlines.py | Shared categories, thresholds, timezone date and maturity classification |
| portal/exports.py | CSV response, fixed columns, exact amount and spreadsheet-text protection |
| portal/middleware.py | View-level DB/storage 503 responses, redacted error-class logs, no-store headers |
| portal/views.py | HTTP orchestration, scope-first fetches, form errors, template contexts and filters |
| portal/urls.py | Route names/paths consumed by templates, tests and scripts |
| portal/management/commands/seed_demo.py | Create missing demo accounts only; never reset old passwords |
| portal/management/commands/seed_scenarios.py | Create 17 synthetic instruments once through real services and save manifest |
| portal/management/commands/due_actions.py | Trusted-operator read-only report, all institutions unless scoped by argument |
| portal/migrations/ | Existing ordered schema history; do not edit applied migrations casually |
| templates/base.html | Common shell, navigation, notices, local stylesheet |
| templates/registration/login.html | Login frontend |
| templates/portal/instrument_form.html | Draft/edit/linked renewal entry |
| templates/portal/instrument_detail.html | Declared values, findings, documents, observations, review, lineage, history |
| templates/portal/release_panel.html | Request/decision/completion forms and preserved evidence |
| templates/portal/instrument_list.html, dashboard.html, release_queue.html | Registers, dashboard and release queue |
| static/css/app.css | Actual frontend styling; no npm build needed |
| scripts/smoke_*.py | Actual HTTP clients, CSRF/cookies, PDF upload/download, lifecycle assertions |
| scripts/evaluate_release.py | Frozen-rule evaluation in isolated in-memory SQLite |
| scripts/build_offline_demo.py | Allowlisted source/wheel copy, hashes and ZIP; excludes runtime data |
| scripts/setup_offline.py | Package integrity, venv/bootstrap install, migration and seeding |
| Start-Demo.ps1, Verify-Demo.ps1 | Windows startup/verification conveniences for source clones |
| Setup-Offline.ps1 | Optional offline-bundle installer; not normal GitHub clone setup |
| evaluation/ | Synthetic ground truth and recorded measurements; read its README before quoting accuracy |

## 3. Entities and relationships

| Entity | Important fields / relationships |
|---|---|
| Institution | Unique code, name |
| UserProfile | One user → one institution; staff role does not require an institution profile |
| Instrument | Institution, bank/reference, amount_paise integer, issue/maturity, review status, created_by, version; optional one-to-one predecessor; superseded_at/released_at |
| Document | Instrument, kind FDR or RELEASE_EVIDENCE, stored file, original name/size/hash, uploader/time |
| ReviewObservation | Instrument and one of its documents; reviewer, optional positive page, severity/comment, explicit resolution metadata |
| ReleaseRequest | Instrument/requester/reason; PENDING/APPROVED/REJECTED/COMPLETED; authority decision metadata; completion metadata and new evidence document |
| AuditEvent | Instrument, actor, action, reason, before/after JSON and time |

INR 500000.25 is stored as 50000025 paise, avoiding binary floating-point arithmetic. Review status and lifecycle are separate: an accepted record can later be superseded or released while retaining its acceptance history.

Current monitoring means status ACCEPTED, no superseded_at and no released_at. It includes matured instruments. APPROVED release requests do not set released_at; completion does. A draft successor does not supersede its parent.

Database constraints cover positive amounts/date order, one-to-one lineage and consistent lifecycle/release metadata. Some cross-row relationships are additionally enforced by services/model clean methods; raw ORM/database writes can bypass portions of that application-level validation. Audit append-only behavior is a supported-workflow guarantee, not a database administrator restriction.

## 4. HTTP routes

These are server-rendered form endpoints with session auth; there is no public JSON API.

| Method | Path | Role / responsibility |
|---|---|---|
| GET/POST | /accounts/login/ | Login form/authentication |
| POST | /accounts/logout/ | Logout |
| GET | / | Authorized register; officer defaults to pending |
| GET | /dashboard/ | Scoped maturity cards |
| GET | /instruments/export.csv | Same scope/filter as current register |
| GET/POST | /instruments/new/ | Institution draft creation |
| GET | /instruments/ID/ | Scoped detail |
| GET/POST | /instruments/ID/edit/ | Institution editable-state updates |
| POST | /instruments/ID/submit/ | Institution submission |
| POST | /instruments/ID/review/ | Independent Officer decision |
| POST | /instruments/ID/observations/ | Officer finding |
| POST | /instruments/ID/observations/OBSERVATION_ID/resolve/ | Officer explicit resolution |
| GET/POST | /instruments/ID/renew/ | Institution new successor proposal |
| GET | /releases/ | Scoped status-filtered queue; staff default pending |
| POST | /instruments/ID/release-requests/ | Institution request |
| POST | /instruments/ID/release-requests/REQUEST_ID/decision/ | Authority authorize/reject |
| POST | /instruments/ID/release-requests/REQUEST_ID/completion/ | Authority evidence-backed completion |
| GET | /documents/ID/download/ | Scoped attachment, nosniff, no-store |

IDs vary between databases. Copy a URL from the app; do not hardcode seeded numeric IDs in new tests/documentation. category/as_of/status query parameters are validated. Forged institution query parameters do not expand CSV/register scope.

## 5. Test map

| Module | What it proves |
|---|---|
| test_submission, test_documents, test_permissions | Initial vertical slice, form/PDF checks, auth/CSRF/scope and history |
| test_validation, test_observations | Two-rule explanations, evidence ownership, blocking/resolution and snapshots |
| test_deadlines, test_dashboard | Boundaries, timezone/date overrides, scoped cards/list/report definitions |
| test_renewals | Lineage, atomic supersession, private-draft visibility, competing/stale requests |
| test_releases | Role independence, states/evidence, conflicts, monitoring and rollback |
| test_exports | Scope/filter parity, quoting/formula protection, precision and historical exclusions |
| test_demo_workflow | Scenario correctness/idempotency/rollback and package integrity checks |
| test_reliability | Injected DB/storage failures, safe responses/logs, no partial state/files |
| test_configuration | Invalid settings fail early; non-DEBUG secret requirement |
| test_evaluation_contract | Frozen labels and old snapshot preservation |
| test_complete_journey | HTTP correction → acceptance → renewal → evidence-backed release on one lineage |

Run one module, for example: .\.venv\Scripts\python.exe manage.py test portal.tests.test_observations --verbosity 2. Tests are not proof of visual correctness or real-world financial/regulatory validity.

## 6. Configuration

| Variable | Demo default | Meaning / caution |
|---|---|---|
| DJANGO_DEBUG | true | Local-only debug; enables labeled report date override |
| DJANGO_SECRET_KEY | local fallback only when DEBUG=true | Must be set for DEBUG=false; never reuse fallback in shared hosting |
| DJANGO_ALLOWED_HOSTS | localhost,127.0.0.1 | Host checks, not a firewall or authentication substitute |
| DJANGO_SECURE_COOKIES | false | Local HTTP convenience; true requires appropriate HTTPS hosting |
| MAX_UPLOAD_MB | 10 | Positive integer; envelope size validation, not full network request limiting |
| BUSINESS_TIMEZONE | Asia/Kolkata | Valid IANA timezone; invalid values fail at startup |
| REMINDER_DAYS | 30,15,7 | Positive thresholds; demonstration configuration, not certified policy |

.env.example is not automatically loaded. A temporary PowerShell example is `$env:BUSINESS_TIMEZONE = 'Asia/Kolkata'`, then start the process from that shell. Restore/remove temporary overrides afterward. Start-Demo/Verify-Demo deliberately use local DEBUG mode; they are not deployment commands.

There is no STATIC_ROOT/reverse-proxy/TLS/production server configuration. Changing DEBUG alone does not create a safe deployment or keep development static serving operational. Do not disable security checks to make a public demo work.

## 7. Smallest safe development loop

1. Select one accepted behavior change and write the expected outcome first.
2. Locate the related route, form, service, model and test from the map above.
3. Preserve scope-first reads, role checks and transaction boundaries. Put new state changes in a service.
4. Add a meaningful regression test that would fail before the intended correction; do not add tests that only repeat CSS or implementation details.
5. Run the focused module, then the full gate before packaging. Restart --noreload server for Python edits and perform the relevant manual flow.
6. If schema changes are justified, create a **new** migration and test both fresh setup and upgrade from a private backup copy. Never rewrite applied history to avoid an error.
7. If rule meaning changes, review ground truth, version new snapshots and preserve historical results. Do not edit labels merely to make a failing implementation pass.
8. Update requirements/docs/evaluation only when actual behavior changes. Rebuild a new archive and verify its fresh setup; an old checksum is expected to become stale after source edits.

GitHub source setup uses requirements.txt and a per-clone .venv; do not expect a committed wheelhouse or package manifest. The offline builder remains optional. Keep reviewed commits and private consistent data backups for recovery. Never edit multiple near-identical clones/dist folders without identifying the authoritative source.
