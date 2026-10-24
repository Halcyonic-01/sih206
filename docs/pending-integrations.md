# OCR, notification and bank-channel handoff

These additions were explicitly requested by Yash after the initial Y1-Y8 build.
They include shared platform/notification integration and the bank email workflow.
They do not publish a regulatory rule set or establish that an external system was
connected. Review the feature branch before merging it with teammates' work.

## Local OCR

Install Tesseract with English language data and Poppler (`pdftoppm`). Set
`OCR_TESSERACT` and `OCR_PDFTOPPM` to absolute executable paths if they are not on
PATH. On Windows the standard Tesseract installation location is also detected.
These native programs are not bundled in the offline ZIP; provision them separately
on an offline target. The portal remains usable manually when either is missing.

OCR runs in a child process with a 45-second deadline. It renders at most five
pages, bounded to 2,500 pixels on the longest side, from a hash-checked PDF of at
most 10 MB. Each renderer/OCR child has an eight-second deadline. English OCR text,
page numbers and an uncalibrated Tesseract score are shown for review. Suggestions
require explicit labels and adequate page scores; conflicting or invalid values
stay unknown. This parser is deliberately conservative: it is not a general bank
layout recognizer, handwriting recognizer or authenticity check. OCR text is
untrusted data and is never executed or interpreted as instructions.

```powershell
.\.venv\Scripts\python.exe manage.py seed_ocr_example
.\.venv\Scripts\python.exe manage.py evaluate_extraction --engine ocr
```

Open `SYNTHETIC-OCR-001` as institution_a, then Documents → Read with local OCR.
Review the source page and choose the editable prefill action. Saving remains a
separate user action. OCR is independent of `AI_ENABLED` and makes no network call.
Runs are logged as `LOCAL_OCR` in `AiRun`; raw OCR text is not persisted in that log.
The synthetic example passed 6/6 labelled fields locally. This is a development
smoke check, not a held-out or representative accuracy evaluation.

## Notifications

`notifications.services.notify(recipients, template, context, key)` writes the
outbox inside the workflow transaction. Submission goes to officers; review goes
to the institution's active users. Only the record ID/reference are included.
Repeated keys cannot create duplicate recipient/channel rows. The inbox and read
acknowledgements are recipient-scoped; delivery operations are officer-only.

```powershell
.\.venv\Scripts\python.exe manage.py run_due_rules
.\.venv\Scripts\python.exe manage.py deliver_notifications
```

Schedule the first command daily and the second every minute using the deployment
scheduler. The command implements configured `REMINDER_DAYS` maturity reminders;
it does not invent a regulatory escalation matrix or working-day SLA calendar.
Failures retry after 1/2/4/8 minutes, then remain FAILED with safe error codes.
The inbox/operations page shows pending, sent, captured and failed states.
SENT email means SMTP relay acceptance, not recipient reading or exactly-once
delivery. A process crash after SMTP acceptance can cause a duplicate retry.

Email delivery is disabled by default. The default backend captures local test
messages in process memory; those are labelled CAPTURED, never externally SENT.
For an approved SMTP service configure the operating-system variables in
`.env.example`, including `DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`
and `NOTIFICATION_EMAIL_ENABLED=true`. Settings now load the ignored root `.env`;
explicit process variables take precedence. See [Supabase setup](supabase.md).
No real email was sent during verification; tests use local capture/mocks.

## Bank confirmation

Officers can request a bank confirmation from the Verification tab. The destination
is read exclusively from operator-controlled `BANK_CONTACTS_JSON`, keyed by IFSC:

```json
{"ABCD0123456":{"email":"branch@example.invalid","source":"Approved directory version","approved":true}}
```

Replace this synthetic example with an independently approved directory outside
Git. The institution cannot set a recipient, and the officer API never returns
the token or OTP. Contact provenance is retained with each request.

```powershell
.\.venv\Scripts\python.exe manage.py deliver_bank_requests
```

The worker emails a signed, 24-hour link and a six-digit OTP. Codes are hashed at
rest. Five bad codes lock the challenge; expiry, replay, duplicate requests and
stale deposit versions are rejected. A new request is limited to three per record
per day. The public form is CSRF-protected, uses no-referrer/no-store and does not
display the institution's declared values. The bank supplies its observed fields.
Negative/mismatched responses retain evidence, create a discrepancy and a blocking
observation when a document exists, and enqueue a notice. No response auto-accepts
a submission or releases funds. Officer acceptance preserves confirmed evidence.

`BANK_CONFIRMATION_SIMULATED=true` is the default. Simulation requires the local
in-memory mail backend, can be exercised by the bank workflow tests, and never
sets CONFIRMED. For a real mailbox integration set the flag false only with
reviewed contacts, production secrets (`DJANGO_DEBUG=false`), a public HTTPS
`BANK_PUBLIC_BASE_URL`, and the approved SMTP backend enabled. Deploying an
accessible service, bank acceptance testing and actual bank responses remain
external prerequisites. This implements email confirmation, not an unspecified
bank HTTP API. Do not treat a synthetic/mock test as a live bank connection.

## Shared integration and obligation coverage

Session endpoints are `/api/auth/csrf/`, `/api/auth/login/`, `/api/auth/logout/`
and `/api/auth/me/`. The frontend uses `src/api/client.ts` and `AuthProvider`, with
same-origin sessions and CSRF; the existing Django sign-in screen is retained.
The JSON login has a per-IP fixed-window throttle. Configure a shared cache for
multiple workers; the inherited template login requires separate production
account-governance review. No SSO, comprehensive platform shell, OpenAPI catalog
or production security certification is claimed by this integration.

`/api/obligations/` and the dashboard now calculate scoped coverage from current
accepted, unexpired holdings and explicitly reviewed stored requirements.
Released, superseded and future-issued holdings are excluded. Coverage end is
the date until which holdings can cover the required amount. Missing/unapproved
rule metadata stays unknown. Exemptions require their existing approval evidence.
The programme-to-required-amount calculator, authoritative policy publication and
complete regulatory checks/escalations still require the rules owner's work.

## External AI smoke check

The existing provider adapter remains disabled unless `AI_ENABLED=true` and an
`ANTHROPIC_API_KEY` are present in the server process environment. Once configured,
an operator can explicitly authorize the seeded synthetic scan:

```powershell
.\.venv\Scripts\python.exe manage.py evaluate_extraction --engine ai --allow-external
```

This sends the synthetic PDF externally and logs the call. Do not run it with real
documents. The development session could not see an Anthropic key, SMTP variables
or bank directory in its process/Windows user/machine environment. No live AI,
SMTP or bank result is claimed. The user must identify the configuration location
and approved bank API/contact source to finish that connection.

## Validation

237 backend tests passed; the final bank hardening changes also receive a focused
rerun. Four browser journeys passed, including local OCR, inbox, reconciliation,
mobile navigation and institution isolation. TypeScript/build and migration checks
passed. Native OCR was exercised against an image-only synthetic PDF. Bank and
SMTP paths were tested locally/mocked. A physically disconnected rehearsal and
representative scan evaluation remain separate acceptance checks.
