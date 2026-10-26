# The audit chain reports a problem

Detected by `python manage.py verify_audit_chain` (exits non-zero), by the auditor's *Verify chain* button, or by
`GET /api/audit/chain/verify/`. Statuses:

| Status / reason | Meaning |
|---|---|
| `broken` · `event_modified` | An audit event no longer matches its seal (changed after sealing, **or** the key is wrong) |
| `broken` · `event_missing` | A seal exists for an event that is gone |
| `broken` · `chain_break` | A link is missing, reordered or inserted before the named event |
| `incomplete` | Events exist without seals (they were created by `bulk_create`, raw SQL, a fixture load, or sealing was interrupted) |

## 1. Stop and keep the evidence

* Do **not** run `seal_audit_chain` yet. It seals whatever is unsealed, so on an `incomplete` chain it could make
  an unexplained row look legitimate (it would only be marked "sealed late").
* Save the full output of `verify_audit_chain` (event ids and reasons) and take a backup of the database and documents
  as they are ([restore runbook](restore-database-and-documents.md)). Note the time.
* Tell the auditor and the portal owner. Treat it as a possible security incident until explained.

## 2. Is it simply the wrong key?

If **every** event from the first one fails with `event_modified`, the key is probably different from the one that sealed
them (a rotated `DJANGO_SECRET_KEY` with no pinned `AUDIT_CHAIN_KEY` is the usual cause; see
[the key runbook](audit-chain-key-rotation.md)). Restore the previous key, restart, verify again. If it now says `OK`, the
chain was never broken.

## 3. Only some events fail

1. Note the first failing `event_id`. Everything after a `chain_break` is reported relative to it, so fix and explain the
   earliest problem first.
2. Look at the event in the auditor screen and in the access log around its time: who was signed in, from where, and which
   exports or downloads happened.
3. Compare with the latest trustworthy backup, restored into a **scratch** database ([restore runbook](restore-database-and-documents.md)):
   * Same event, different `reason`, `before` or `after` → it was edited after sealing.
   * Event missing in the live database but present in the backup → it was deleted.
4. Decide with the portal owner:
   * **Restore the original** values from the backup into the live row using an administrator database session, then verify
     again. The record of the incident (who, when, what was changed) is kept outside the portal, in your incident notes.
   * **If no trustworthy backup exists**, the event cannot be proved. Start a fresh database and keep the old one read-only
     as evidence.

## 4. `incomplete` only (no `broken`)

Find out why rows are unsealed before sealing them. Legitimate causes: a fixture load, an import run during a maintenance
window, or a crash between writing the event and its seal. If you can name the cause and the rows are expected, run:

```bash
python manage.py seal_audit_chain
python manage.py verify_audit_chain
```

Those events are marked "sealed late". If you cannot name the cause, treat it as step 3.

## 5. Close it

`verify_audit_chain` says `OK`, the auditor has re-run *Verify chain*, and the incident notes say what happened, what was
restored and who agreed. Do not "fix" a chain by deleting seals or events: the application refuses it, and doing it in the
database destroys the evidence you are trying to protect.
