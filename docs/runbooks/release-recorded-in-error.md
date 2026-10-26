# A release was recorded in error

A release goes through: request → clearances → officer review → authority authorisation → letter → completion.
Which step you are at decides what can be done. **There is no "undo" for authorisation or completion in the portal today**,
and the portal never executes a payment, so the first question is always whether any money moved.

## 1. Contain (any step)

1. Tell the authority and the portal owner immediately. Write down the case number, the instrument reference and the time.
2. If a **letter was issued**, an authority user who is **not the requester** revokes it on the case page
   (*Revoke letter*, with a reason). The public `/verify/<token>` page then shows "Revoked — do not rely on this letter".
   Do this first: it is the only thing that stops others relying on the letter.
3. Tell the institution and, where a bank or PFMS refund reference was entered, the people who act on it, so nothing is
   paid or discharged on the strength of the portal record.

## 2. Work out what was recorded

| Where the case is | What exists | What you can still do in the portal |
|---|---|---|
| Requested, clearances pending | A request only | Reject it (authority). Nothing to repair |
| Officer review done | Clearances, penalty decisions | Reject it (authority) |
| Authorised, no letter | An authorisation event | Approve and reject are only offered while the case is pending, so there is no cancel. Completion needs an issued letter, so **do not issue one**; the case stays "authorised, completion pending" and the instrument stays in monitoring |
| Letter issued, not completed | Letter and public token | Revoke the letter (step 1). Completion is only offered while the letter is not revoked, so this also stops completion |
| **Completed** | `released_at` set on the instrument, completion evidence PDF, `RELEASE_COMPLETED` audit event | Revoke the letter; the instrument stays out of maturity monitoring |

Never delete the release request, the evidence document or any audit row: they are the record of the mistake.

## 3. Restoring monitoring after a completed release (supervised data correction)

The portal has no reopen action, so putting the instrument back into monitoring needs a one-off correction by the technical
owner. It must be agreed in writing by the authority and the officer, and performed by one person while a second watches.

1. Back up the database and documents ([restore runbook](restore-database-and-documents.md)) and record the audit head.
2. Prepare the correction as a short script reviewed by the second person, run in `manage.py shell`. It must:
   * clear `released_at` on the instrument and move the release request out of `COMPLETED` in a way that keeps the original
     request, notes and evidence file;
   * write an explanatory audit event with `portal.services.event(...)` (so it is sealed in the chain), stating the case,
     the reason and who approved. Never `bulk_create` audit events and never edit `AuditEvent` or `AuditSeal` rows;
   * run inside one transaction.
3. Run `python manage.py verify_audit_chain` (must say `OK`), open the record as the officer and the institution, and check
   that maturity monitoring and reminders show it again.
4. Keep the approvals and the script with the incident notes.

## 4. After the incident

Record what allowed the mistake (wrong case selected, a single approver, documents changed after approval) and raise it as an
issue. Two controls proposed for this are a second signature above an amount, and tying an authorisation to a fingerprint of
what was approved; both are listed as proposals, not features.
