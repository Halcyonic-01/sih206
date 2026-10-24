# Daily rules and notifications (K6)

```bash
python manage.py run_due_rules                   # today, business timezone (Asia/Kolkata)
python manage.py run_due_rules --as-of 2026-11-01   # replay a date (PS scenario 4)
python manage.py run_due_rules --dry-run          # list what would be queued, write nothing
python manage.py run_due_rules --institution A --only maturity
python manage.py send_notifications               # email retries; run every few minutes
```

Idempotent: every notification carries a key (record, rule, boundary crossed), so running twice in a day, or
again after a missed day, never duplicates anything. A rule fires when its boundary has been **crossed**, so a missed
run catches up with one notification per rule. One failing rule group does not stop the others; the command
prints the error and exits non-zero so the scheduler can alert.

| Rule | Fires when | Recipients | Key |
|---|---|---|---|
| Maturity reminder | days left ≤ 90, 60, 30, 7 (smallest crossed, once each) | institution contacts; plus dealing officers from T−30 | `instrument:<id>:maturity:T-<n>:<maturity date>` |
| Renewal overdue | ≥ 1 day past maturity, still current | institution, officers, authority (regional head) | `instrument:<id>:renewal-overdue:<date>` |
| Penalty review (APH 7.7) | ≥ 30 days past maturity, still current | officers | `instrument:<id>:penalty-review:<date>` |
| Proof due | day 7, 12, 15 after `intimation_date` while the obligation is `DUE` or `PARTIALLY_MET` | institution contacts | `obligation:<id>:proof-due:day<n>:<intimation>` |
| SLA: submission | submitted record waiting > 7 working days | authority (supervisor) | `instrument:<id>:sla-submission:<submitted date>` |
| SLA: corrections | changes requested ≥ 15 days / ≥ 30 days ago | institution / officers | `instrument:<id>:sla-correction:<n>:<date>` |
| SLA: clearance | open clearance task > 7 / > 14 working days | the unit / authority | `clearance:<task id>:sla:<n>:<opened date>` |

Skipped: records that are not current (draft, submitted, superseded, released), records with a pending or
authorised release, and (once portal migration 0005 adds `Instrument.obligation`) holdings that mature after the
obligation term ends.

## Configuration: `RuleSet` code `escalation-matrix` (contract for S2)

Defaults live in `notifications/rules.py`. The newest `RuleSet` with code `escalation-matrix` (or
`escalation_matrix`) effective on the evaluation date overrides any of these keys; unknown keys are ignored:

```json
{
  "maturity_reminder_days": [90, 60, 30, 7],
  "maturity_officer_days": [30, 7],
  "renewal_overdue_after_days": 1,
  "penalty_review_after_days": 30,
  "proof_reminder_days": [7, 12, 15],
  "proof_penalty_label": "10% / 20% per APH 2.25(f)",
  "sla": {"submission_working_days": 7, "correction_days": [15, 30], "clearance_working_days": [7, 14]},
  "holidays": ["2026-11-12"]
}
```

Working days are Monday to Friday minus `holidays` (no gazetted-holiday calendar is built in).
The values are a proposal for AICTE to confirm, not validated regulatory timelines.

## Open dependencies

* **S5 `casework.ClearanceTask`**: `open_clearance_tasks()` in `notifications/rules.py` (marked `TODO(S5)`) assumes
  `unit`, `status`, `created_at` and a `release.instrument` link, and returns nothing if they differ. Adjust the
  field names there when S5 merges.
* **S2**: nothing else is needed. The proof rule uses `DepositObligation.status` and `intimation_date`; if S2 keeps
  `status` up to date (MET when covered), reminders stop on their own.
* "Dealing officer" and "supervisor" are mapped to the Officer and Authority roles; there is no per-officer
  assignment model yet.

## Running it on a schedule

* Linux/macOS cron: `5 6 * * * cd /srv/fdr && .venv/bin/python manage.py run_due_rules >> logs/rules.log 2>&1`
  and `*/5 * * * * ... manage.py send_notifications`.
* systemd: a `oneshot` service plus a daily `OnCalendar=*-*-* 06:05:00 Asia/Kolkata` timer.
* Windows Task Scheduler: action `.venv\Scripts\python.exe manage.py run_due_rules` in the project folder, daily.
