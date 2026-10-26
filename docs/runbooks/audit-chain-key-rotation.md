# Rotate the audit chain key

**Read this before changing `AUDIT_CHAIN_KEY` or `DJANGO_SECRET_KEY`.** Every audit event is sealed with
`HMAC-SHA256(AUDIT_CHAIN_KEY, previous hash | event)` ([api-conventions](../api-conventions.md), "Audit hash chain").
The seal does not record which key made it, so **a different key makes every existing seal fail verification**
(`event_modified` for each event). There is no re-key command today.

## The trap: the fallback key

When `AUDIT_CHAIN_KEY` is empty, `config/settings.py` derives it from `DJANGO_SECRET_KEY`. So rotating the Django
secret key silently changes the audit key too. Check first:

```bash
python manage.py shell -c "import os; print('AUDIT_CHAIN_KEY set explicitly:', bool(os.environ.get('AUDIT_CHAIN_KEY')))"
```

If it prints `False`, pin the current derived value **before** rotating the secret key. On the server only, and without
saving the output anywhere but your secret store:

```bash
python manage.py shell -c "from django.conf import settings; print(settings.AUDIT_CHAIN_KEY)"
```

Put that value in the `AUDIT_CHAIN_KEY` environment variable (or `.env`), restart, run
`python manage.py verify_audit_chain` (must say `OK`), and only then rotate `DJANGO_SECRET_KEY`.
Rotating the secret key also signs out every user and invalidates signed links (bank confirmation links, for example).

## Do you need to rotate the audit key at all?

* **Only the Django secret key changed, and `AUDIT_CHAIN_KEY` is pinned:** nothing to do for the chain.
* **The audit key may have been exposed:** a person holding it could forge seals for edited events, so history written
  before the exposure can no longer be trusted by the chain alone. Go to "After an exposure".
* **A routine rotation policy:** not recommended with the current design, because it re-seals history as "sealed late".
  Wait for a key identifier on each seal (proposed, not built).

## After an exposure

1. **Freeze writes.** Put the portal in maintenance (stop the web process or block it at the proxy).
2. **Prove the chain is intact under the old key.** `python manage.py verify_audit_chain` must say `OK`. If it does not,
   stop and use [the broken-chain runbook](broken-audit-chain.md) first: do not re-seal over a problem.
3. **Keep the evidence.** Back up database and documents ([restore runbook](restore-database-and-documents.md)), have the
   auditor export the audit trail CSV (it is access-logged), and record the chain head printed by `verify_audit_chain`.
   Store these offline, with the old key in escrow, as the proof for everything up to now.
4. **Generate the new key** (64 hex characters) and put it in the secret store:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
5. **Re-seal under the new key.** `AuditSeal` rows are append-only: the application refuses to delete them. This step is a
   database-administrator operation and needs two people: with the backup from step 3 in hand, empty the seal table
   (`audit_auditseal`, inside the `portal_app` schema on Supabase), set the new `AUDIT_CHAIN_KEY`, restart, and run:
   ```bash
   python manage.py seal_audit_chain
   python manage.py verify_audit_chain
   ```
   Every event is now marked **sealed late**: it proves nothing changed *since the re-seal*, not that events were correct when
   written. The step-3 evidence is what vouches for the earlier period.
6. **Reopen** and tell the auditor when the new chain starts and where the old evidence is kept.

Never run step 5 without step 2 and step 3: re-sealing would turn tampering into a clean-looking chain.

## Encryption key (not implemented yet)

Encryption at rest for stored documents is a proposal, not a feature. When it ships, this runbook must gain a section for
rotating that key (a key identifier on each stored file, and re-encrypting files in the background). Until then there is no
document encryption key to rotate.
