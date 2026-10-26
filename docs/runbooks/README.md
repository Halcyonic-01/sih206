# Operations runbooks

Short, step-by-step procedures for the situations an operator is most likely to face. Each one says what to check first,
what to run, how to know it worked, and what **not** to do. They describe what the portal does today; where a safe
procedure needs a feature that does not exist yet, the runbook says so instead of inventing a command.

| Runbook | Use it when |
|---|---|
| [Rotate the audit chain key](audit-chain-key-rotation.md) | `AUDIT_CHAIN_KEY` (or `DJANGO_SECRET_KEY`, which it falls back to) is exposed, or must change |
| [Restore the database and the documents](restore-database-and-documents.md) | A server or Supabase project is lost, or a restore drill is due |
| [The audit chain reports a problem](broken-audit-chain.md) | `verify_audit_chain` exits non-zero or the auditor's *Verify chain* shows `broken` / `incomplete` |
| [A release was recorded in error](release-recorded-in-error.md) | A release was authorised, a letter issued or a completion recorded for the wrong case |

## Rules that apply to every runbook

* Work on the real data only with a second person watching, and write down the time, who did what and the command output.
* Take a backup first ([restore runbook](restore-database-and-documents.md), section "Back up"). Database and `data/documents/`
  are always copied **together**.
* Never edit or delete `AuditEvent` or `AuditSeal` rows to "tidy up". The chain exists to show what happened, including the mistake.
* Never paste a database URL, key, password or the contents of `.env` into chat, tickets or screenshots.
* Everything here is for the prototype's synthetic data. Real deposit data needs the production hardening items in the README first.
