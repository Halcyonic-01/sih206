# Feature 3: personalized Monday email digest

27 October 2026. **Current implementation: D1–D4 local code is integrated.** The original pure synthetic preview is preserved. Trusted ORM sources, durable preferences, a protected own-account preview, Monday dispatch and the existing leased email worker are implemented. Actual external SMTP delivery and an operating-system scheduled task have not been configured or exercised. The existing local launcher and Docker worker now invoke the digest dispatcher before their five-minute email worker, so their daily-rule stamp cannot delay Monday mail until Tuesday. Feature 1 remains paused.

The sections below document the original staged design; see the current implementation and runbook appended at the end for what now exists.

## Research and current implementation

The project already has Kushagra's transactional outbox: `notifications.service.notify(recipients, template, context, key)` creates separate per-recipient/per-channel rows. `Notification` has a unique constraint on `(idempotency_key, channel, recipient_key)`; keys allow 200 characters. `deliver_pending` uses a lease and bounded retries (five attempts, increasing backoff). `send_notifications` retries queued mail; `run_due_rules` evaluates daily maturity/proof/SLA rules. Adding another SMTP sender or scheduling library would duplicate this infrastructure.

Django supports text messages and multipart text/HTML messages and provides a memory backend suitable for delivery tests. That supports reusing the current plain-text sender first and treating the new HTML preview as an optional later presentation upgrade, rather than introducing an email provider. The current sender footer says the message contains no account/deposit details; before enabling personalized counts, agree accurate privacy wording with Kushagra. [Django 5.2 email documentation](https://docs.djangoproject.com/en/5.2/topics/email/).

Use timezone-aware instants, convert them to the business timezone for Monday/week/month boundaries, and retain UTC storage. Python's standard `zoneinfo` supplies the IANA timezone implementation; the project already pins `tzdata` for Windows. No new timezone dependency is needed. [Django 5.2 timezone documentation](https://docs.djangoproject.com/en/5.2/topics/i18n/timezones/), [Python zoneinfo](https://docs.python.org/3/library/zoneinfo.html).

Implementation ownership follows the private allocation PDFs: notifications, roles and scheduling belong to Kushagra; Saksham owns release cases, clearances and process KPIs; Yash owns records and verification. The user authorized this new feature. This first slice uses new files only and leaves the shared platform intact; later delivery/scope contracts must be agreed with their owners.

## Product behavior

Propose Monday **09:00 Asia/Kolkata**, configurable at the future dispatcher rather than tied to server timezone. The user specified Monday but has not agreed a time. Nothing is scheduled by this first slice. Missed runs should be recoverable within the current business week without sending seven separate daily digests.

Each active user with one recognized role, an eligible email address and digest preference receives at most one prepared weekly digest. Digest preference and email verification/eligibility must come from trusted server data, not a browser body. Opt-out and no-email states must skip delivery without disabling consequential individual workflow notifications.

| Role | Minimal digest content | Source and exact meaning |
|---|---|---|
| Institution | Deposits expiring in the rest of this calendar month; observations needing its action | Current accepted holdings only, maturity from the as-of business date through month end; exclude released/superseded/private foreign records. Unresolved observations count only when the institution can act. |
| Officer | Pending submissions; unresolved reconciliation mismatches; average review time last week | Scoped submitted records; current unresolved discrepancy interpretation from verification, not a count of every historical discrepancy event. Mean elapsed submission-to-acceptance days for acceptances in the previous week with complete histories. |
| Authority | Cases currently ready for its decision; recorded unresolved PGRC escalations | Use server-computed readiness/independence gates. An old/open PGRC task alone is not proof that an escalation happened. |
| Clearance | Open tasks assigned to its actual unit | Enforce `access.UnitAssignment` and case scope; reject another unit's facts. |
| Auditor | Recorded unresolved audit alerts, when a trustworthy alert source exists | The project has audit/access screens but no assumed incident register. Show unavailable until that source contract exists; never invent a broken-chain count. |

The current platform has no individual officer-assignment model, so an officer digest initially means the officer's authorized scope, not a claim that every listed item is personally assigned. Where no validated escalation/incident adapter exists, display **unavailable**, not zero. A statement-confirmed or simulated record is not independently bank-authenticated.

“Expiring this month” here deliberately means **today through month end**; already matured earlier-this-month records remain in existing overdue views rather than being counted again. The UI/email copy must retain that distinction.

Previous-week review cohort is the half-open interval `[previous Monday 00:00 IST, current Monday 00:00 IST)`, selected by acceptance timestamp. Duration runs from the accepted submission cycle's real submitted timestamp to acceptance; it is calendar elapsed time, not working-day SLA. Unknown/incomplete histories produce no numeric average. A known empty cohort produces unavailable with sample count zero, not “0 days”. Average rounds half-up to one decimal day. The example 1.8 is demonstrated by synthetic labelled durations; it is not measured production performance.

## D1 implemented: pure preparation and labelled scenarios

New files:

- `notifications/digest.py`: strict recipient/role/source snapshot contract, declared-scope/unit consistency checks, Monday IST windows, bounded metric calculations, deterministic weekly identity, safe fixed-route portal links, and text/HTML previews. No Django imports, queries, persistence, provider requests or send functions.
- `notifications/tests/test_digest.py`: 18 focused tests, including the labelled scenarios and safety boundaries.
- `docs/digests/scenarios.json`: nine invented CC0 scenarios covering all five roles, zero work, missing sources and missing review cohort; author-labelled, not independently reviewed.

Entrypoint:

```python
build_digest(recipient_snapshot, synthetic_facts,
             as_of=aware_timestamp, portal_base_url=trusted_configuration_origin)
```

All snapshots in D1 must carry `simulation_label="SIMULATED"`. The body labels synthetic content, and `delivery_state` is always `PREVIEW_ONLY`. This prototype does not accept real applicant document text, balances, names, references, credentials or email addresses. It uses counts, numeric surrogate IDs and dated state facts. Sources are explicit lists/tuples (maximum 5,000 rows per source) or `None`; omitted/None means unavailable. A supplied list represents a complete scoped source, never a silently truncated first page. A future adapter must either provide complete rows or an agreed trusted aggregation contract; it must not truncate and pretend the result is complete.

Inputs are **not authenticated facts**. Scope identity checks catch inconsistent supplied rows but cannot prove a user owns a declared institution. The future ORM adapter remains responsible for authentication, role assignment, permissions, query scoping and source completeness. Records cannot be counted twice within a source; invalid statuses, booleans, future events, negative durations or foreign institutions/units fail explicitly.

Only the role's minimal source fields are accepted; unexpected raw context fields are rejected. Rendered content contains no arbitrary narrative or document quotations. All HTML text and href values are escaped; links are generated from a trusted configured HTTPS origin (or explicit local loopback HTTP for demos) plus a fixed known role route. No user-selected redirect, credential-bearing URL, query, fragment or external links are accepted. The builder makes no HTTP request. Source links still require sign-in and server authorization.

The weekly key format is `weekly-digest-v1:u:<recipient ID>:week:<Monday date>`, within the existing 200-character limit. It remains unchanged for retries and changes for a new recipient/week. **A pure key is not delivery idempotency**: only the later durable outbox uniqueness/frozen snapshot transaction can enforce queue deduplication. SMTP itself cannot guarantee exactly-once delivery if a sender crashes after acceptance and before recording success.

Verification:

```powershell
$env:DATABASE_BACKEND='sqlite'
.\.venv\Scripts\python.exe manage.py test notifications.tests.test_digest --noinput
```

Actual result: **18 tests passed in 0.018 seconds**. Covers exact example counts, unknown versus zero, all roles, scope/unit leaks, inactive/ambiguous/opted-out/no-email users, IST/UTC equivalence, Monday/leap/month/year boundaries, half-open review cohort, incomplete history, duplicate rows, future/negative dates, deterministic weekly key, safe links and a patched send function proving that preparation sends nothing. No SMTP or delivered-email claim is made.

## D2 next: trusted scoped fact adapters and preview

Create a separate digest source adapter after agreeing contracts; do not embed queries in `digest.py`.

1. Resolve the actual active user using the existing `role()` and appropriate institution/unit/scoped helpers. Exclude no-role or ambiguous-role memberships. Validate real email eligibility and opt-out source.
2. Obtain each metric from authorized records only, with the same frozen as-of instant and no unbounded joins/N+1 queries. Institution scopes must be one institution; staff scopes must come from server helpers, never request-supplied IDs. Recheck independent authority actions/readiness per recipient.
3. Coordinate unresolved discrepancy/current evidence interpretation with Yash. Do not count append-only historical mismatches as unresolved after a later verified resolution.
4. Coordinate accepted submission-cycle timestamps with Saksham's KPI adapter; disclose incomplete cohorts. The pure synthetic duration inputs are not a substitute for verified event history.
5. Establish an explicit recorded-escalation source for PGRC and an audit-alert source. Existing SLA-age notifications alone must not be silently promoted to active escalation records. Until agreed, return unavailable.
6. Add an officer-authorized synthetic preview command/API only if needed, with no queue/send side effects and logged staff reads. No new public endpoint.

Acceptance: allowed/denied/foreign institution and clearance-unit tests; private drafts excluded from staff metrics; pagination/row bounds never create a false complete count; source failure returns unavailable; duplicate joins do not inflate totals; retrying preview creates no notifications.

## D3 next: outbox, preference and Monday dispatch

Coordinate these changes with Kushagra before editing shared files:

- A default-off `WEEKLY_DIGEST_ENABLED` setting; proposal of Monday 09:00 IST and catch-up policy.
- Persist digest preference independently of session/browser language. Browser Hindi preference is currently local-only and cannot determine email language; initial mail can stay English until a server preference is agreed.
- A canonical `weekly_digest` template and accurate aggregate-data footer. The current sender sends plain text; adding multipart HTML requires explicit sender and test changes, not just passing HTML into a plain-text body.
- Trusted recipient enumeration with an explicit dry run. Prepare one frozen as-of snapshot/body and call the existing transactional outbox under the deterministic recipient/week key. Existing uniqueness should be reused instead of a duplicate delivery table unless a demonstrated requirement needs one.
- Persist or otherwise unambiguously record the selected scope/role/template/snapshot fingerprints for queued mail. Retries use the frozen body, not new counts under the old key.
- **Before any actual send**, recheck active status, role, institution/unit scope, preference and current email ownership/eligibility. If a user changes roles/scope or opts out after enqueue, suppress the stale digest; do not send its old scope to the new address. Agree a cancellation/suppression representation because current Notification statuses do not include CANCELLED. Do not rewrite historical delivered messages or bypass existing individual notification rules.
- Extend existing deployment scheduling, not the app's request path: a systemd/cron/Windows Task Scheduler job calls a management command; `send_notifications` remains the retry worker. Do not introduce Celery or a Codex reminder/automation for this product feature.
- Document missed-Monday recovery, disabled flag, invalid recipient and failed-run behavior. Avoid automatic historical-week mail floods. Retrying a week cannot create another outbox row for the same recipient/channel/key.

Acceptance: repeated/overlapping dispatcher runs create one email outbox row per eligible recipient/week, transaction failures roll back, preferences/role changes suppress queued stale content, one bad source/user does not expose another user's counts, and retry success/failure/attempt exhaustion remain visible. Local memory-backend tests send no external mail.

## D4 next: end-to-end verification and demonstration

Use a fresh synthetic database and memory backend/Mailpit for institution, officer, authority, each clearance unit and auditor. Demonstrate personalized counts, unavailable metrics, Monday IST boundaries, suppressed recipients, reruns/retries and the protected portal links. Verify rendered plain text and any separately approved multipart HTML. Run the existing notification, scope, backend and browser regressions, then a controlled synthetic SMTP check only with explicit authorization and suitable test recipients. Real-user mailing must not be claimed until these checks pass.

Remaining product decisions: sending hour, whether an all-zero digest should be sent (recommend yes with a short “no recorded work” message), opt-out semantics, email-language preferences, retention of aggregate snapshots, exact escalation/incident sources and role-change suppression behavior. These are documented choices, not silently assumed integrations.


## Current implementation and runbook — 27 October 2026

The user subsequently authorized completing Feature 3, including its notification/platform integration. No new dependency, competing SMTP sender, Celery service, public endpoint, real mailing or environment edit was introduced.

### Implemented files

- `notifications/digest_sources.py`: server role/institution/unit scoping; bounded complete sources; current accepted holdings; actionable correction observations; submitted review queue; latest simulated statement discrepancy plus current discrepancy status; real preceding-submission/acceptance event pairing. Authority uses the existing case action computation, preserving all independent review gates. Clearance uses only the assigned unit. Missing canonical PGRC-escalation and auditor-incident registers remain unavailable. General sources cap at 5,000 rows; authority readiness caps at 50 pending cases because its existing assessment is expensive. Overflow returns unavailable, never a truncated count. Database failures prevent queueing that recipient.
- `notifications/digest_dispatch.py`: one frozen email outbox row per recipient/week via the existing database uniqueness constraint. Monday 09:00 IST is the adopted default; after that instant, later runs in the same week catch up once. No historical week flood. No in-app digest row and no immediate send-on-commit. No-role, ambiguous, missing-unit/institution accounts skip. A bad recipient/source is isolated and counted failed, without logging addresses or content.
- `notifications/models.py` and `notifications/migrations/0002_digestpreference.py`: saved optional-digest opt-out and optimistic preference version. Existing consequential workflow notifications are unaffected. A missing preference defaults enabled, but the global sending flag defaults off. Migration was tested on disposable test databases only.
- `notifications/digest_views.py` and URL registration: signed-in GET/PATCH `/api/notifications/digest-preference/`; GET `/api/notifications/digest-preview/`. No requested owner/scope accepted; preview rejects query overrides. PATCH takes exactly `enabled` (boolean) and `version` (nonnegative integer), with 409 on stale writes. Version zero means no saved preference yet. Wrong/no role is denied; invalid input is 400; source failure is safe 503. Reads and changes are logged fail-closed in the append-only access log. Preference changes use `DIGEST_PREFERENCE_CHANGED`, since shared instrument workflow audit events require a real instrument and are unsuitable for account preferences.
- `notifications/service.py`: weekly email footer accurately describes aggregate activity. Before every attempt, the worker rechecks global flag, actual active user, single role, institution/unit authorization identity, email and preference/version. A changed recipient is marked FAILED with explicit SUPPRESSED reason, never SENT. Staff scope fingerprints use the actual global role/unit authorization policy, not the changing set of institutions with submitted records. SMTP failures retain the existing lease/retry/backoff and frozen body. SMTP cannot promise exactly-once delivery after a crash following server acceptance.
- `notifications/management/commands/send_weekly_digests.py`: default dry-run; `--queue` requires the global flag. Source failures exit unsuccessfully. Existing `run_due_rules` invokes dispatch only when the flag is enabled and the command is a normal current unfiltered run; historical `--as-of`, institution and rule filters never dispatch a global digest. The existing `send_notifications` worker performs delivery.
- `frontend/src/features/notifications/WeeklyDigest.tsx`: Notifications → Weekly email digest; saved opt-out; explicit enabled/disabled server status; own preview without sending; loading, retry and stale-write states. UI labels translated into Hindi; the email/preview content intentionally remains English and says so.

### Run locally without external mail

```powershell
# Use the existing project virtual environment and your intended local database.
# Inspect showmigrations first. This applies only the additive preference migration.
.\.venv\Scripts\python.exe manage.py showmigrations notifications
.\.venv\Scripts\python.exe manage.py migrate
# Preview command never sends or queues. Before Monday 09:00 IST it reports not_due.
.\.venv\Scripts\python.exe manage.py send_weekly_digests
```

Open Notifications → Weekly email digest, inspect server dispatch state, click Preview my digest and toggle the checkbox to save your preference. Each account sees only its own authorized snapshot. Previewing never creates an email row. If the account lacks an eligible email or opts out, preview explains ineligibility. Staff and institution previews use recorded facts; empty or unsupported sources never invent the example numbers.

### Enable delivery deliberately on a deployment

Set `WEEKLY_DIGEST_ENABLED=true` only after reviewing accounts, eligible email addresses and SMTP configuration. Keep `PORTAL_BASE_URL` as the actual trusted HTTPS origin. This task did **not** modify `.env`, enable the flag, send real messages or install an operating-system scheduled task.

Run these commands from the repository with its virtual environment:

```powershell
.\.venv\Scripts\python.exe manage.py send_weekly_digests --queue
.\.venv\Scripts\python.exe manage.py send_notifications
```

The bundled `scripts/run_portal.py` local launcher and Docker worker invoke `send_weekly_digests --queue` before `send_notifications` on their existing five-minute loop. With the flag enabled, this reaches Monday 09:00 IST independently of the daily-rule stamp. No separate operating-system task is needed while that launcher/worker is running. If deploying with a different process supervisor, configure its existing scheduler to run `send_weekly_digests --queue` hourly and `send_notifications` every few minutes; alternatively use unfiltered current `run_due_rules` hourly alongside the worker. Use the same application environment/database and repository working directory. An ordinary daily scheduler running before Monday 09:00 will catch up on its following run, so hourly is recommended. The dispatcher uses the business timezone irrespective of server timezone. The commands are safe to rerun; pending/failed/sent rows retain their original weekly identity. Review FAILED/SUPPRESSED rows through the existing delivery-status view. A suppressed weekly row is deliberately not recreated under another address/scope in the same week; a new week creates a new key.

### Local verification and limitations

`notifications.tests.test_digest`, `test_digest_integration` and `test_service` passed together (58 tests, 9.215 seconds), including the final repeat-dispatch optimization assertion; final run is recorded in `data/digest-focused-final.log`. Real ORM fixtures also verified 1.8-day previous-week mean with a current-week boundary exclusion, actual clearance unit scoping, and delegation to the existing authority action gate (gate internals remain covered by existing casework tests). Repeat scheduler ticks now recognize an existing frozen weekly row before rebuilding expensive case sources. Two notification component test files passed 8 tests in 34.66 seconds. Integration uses Django's in-memory email backend, not external SMTP. Tested scope isolation, opt-out/version errors, own preview, unknown metrics, frozen deduplication, next-week identity, Monday/catch-up behavior, SMTP retry, suppression after role/email/institution/preference/activation changes, skipped invalid accounts and scheduler replay/filter safety. Root agent records the final full-regression result separately.

The original nine scenario labels remain author-created synthetic data. No independent ground-truth evaluation, provider email delivery, Windows Task Scheduler installation, email verification flow, persisted language preference or production load claim is made. PGRC escalation and auditor incident counts remain unavailable until canonical records exist. Email ownership uses the current stored user email (no email-verification subsystem is invented). Privacy-safe totals exclude raw institution names, document text, monetary balances and deposit references.
