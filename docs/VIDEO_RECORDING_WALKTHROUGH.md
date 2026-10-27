# Pramaan: beginner recording script

Prepared against main `5097c47`, 25 October 2026. UI labels and form logic were checked in source and the local synthetic database was inspected. Browser-control tools failed to initialize, so this is not a claim of a completed visual rehearsal. No records were changed to prepare this script.

## Before recording

Allow 20–30 minutes to rehearse; aim for an edited 7–9 minute video. Showing every role and completing a live release needs more time than a five-minute overview. If five minutes is mandatory, use the condensed order at the end.

1. Open http://127.0.0.1:8010/login. Use the current React interface, not `/legacy/`.
2. Keep this document on another screen or print it. Close `.env`, terminals showing keys, WhatsApp, and password files before screen recording. Turn off desktop notifications.
3. Read passwords privately from `data/demo-credentials.txt`, `data/authority-credentials.txt`, and `data/staff-credentials.txt`. Do not record password files or say passwords aloud.
4. Use ONE portal tab for the recording. Switching tabs does not switch users: browser tabs share the session. For each role change, top-right **Account menu → Sign out**, then sign in as the next user. Cut the login pauses from your video.
5. Keep `fixtures/release-evidence.pdf` ready in the file picker. Use synthetic documents only.
6. Confirm the release sample is still available: institution_a → Records → search `PS7-RELEASE-READY` → press Enter. It should be ACCEPTED and show **Request release**. At inspection, its record ID was 44 and it had no release case. IDs may vary on other machines.
7. Do not submit its release during a practice run unless you intend to continue that same saved case during recording. Requests and decisions persist. Reseeding does not reset them. For a second take use the saved state or arrange a separate disposable demo database; never delete your working database.
8. Capture at 1080p, browser zoom around 100%, pointer visible. Pause briefly after each click. Record a short microphone test first.

## Roles in the story

| Username | What you demonstrate |
|---|---|
| institution_a | Submission, document visibility, release request |
| officer | Scrutiny, obligation review, reports, release checklist review |
| clearance_pgrc | PGRC clearance |
| clearance_vigilance | Vigilance clearance |
| clearance_grants | Grants clearance |
| authority | Independent authorization, letter and completion |
| auditor | Audit events, access records and integrity checks |
| institution_b | Separation of institution data |

Start with the institution, because it starts the real workflow. Do not begin as authority and approve an unexplained case.

## Scene 1 — introduce the problem (20 seconds)

Sign in as **institution_a**. Click **Dashboard** in the left menu.

Say: “Pramaan brings security deposits and their supporting documents into one place. Today, we will follow a deposit from institution review to an authorized release. All the records in this video are synthetic demonstration data.”

Point to the dashboard counts and maturity chart. Do not memorize counts: they change as you use the demo.

Say: “The dashboard shows active deposits, upcoming maturities, and cases that need attention. Staff can act before a deposit is missed.”

## Scene 2 — a record and its evidence (40 seconds)

1. Click **Records** on the left.
2. In **Search deposit records**, type `PS7-RELEASE-READY` and press Enter or the search icon.
3. Click the reference in the results.
4. Point to **Details**, then click **Documents (...)**.
5. Select a supporting document from the **Supporting document** dropdown. Wait for the PDF to load. If the viewer fails, use the available protected document download and open it; rehearse this before recording.
6. Click **Checks & observations**, then **History**.

Say: “Each deposit keeps its dates, amount, supporting PDFs, checks, and history together. A reviewer can go back to the evidence instead of relying on a spreadsheet entry. Accepted means accepted for administrative tracking; it does not mean a bank has authenticated the deposit.”

## Optional scene — demonstrate the new-deposit form (adds 60–90 seconds)

Use this for a longer walkthrough. It is a separate sample; the release story below uses the already accepted PS7 sample. Do not imply this new deposit was instantly approved or matured.

Institution_a → **Records → New deposit**. Fill the modal:

| Field | Demonstration value |
|---|---|
| Deposit type | FDR |
| Instrument reference | VIDEO-FDR-001; use VIDEO-FDR-002 for a second unique take |
| Issuing bank | Fictional Demo Bank |
| Amount (INR) | 500000.00 |
| Issue / payment date | 2026-10-01 |
| Maturity / recorded end date | 2036-10-01 |
| IFSC | SBIN0001234 — format example only |
| Branch | Synthetic branch |
| Holder names | Fictional Trust; AICTE |
| Declared lien status | Lien marked |
| Obligation ID (optional) | Leave blank for this separate data-entry demonstration |
| Supporting PDF | `fixtures/sample-fdr.pdf` |

The chosen PDF is an upload demonstration, not verified ground truth for these form values. Say: “These are synthetic declared values. A reviewer must compare them with the document before acceptance.”

Click **Save draft**, then **Submit for review → Record action**. Say: “The institution saves a draft and explicitly submits it. Submission does not grant approval.” Stop if an error appears; inspect it rather than clicking repeatedly.

## Scene 3 — officer review and obligation visibility (60 seconds)

Sign out; sign in as **officer**.

If you used the optional new-deposit scene: Records → search its unique reference → open → Documents → inspect PDF; Checks & observations → inspect findings. You can click **Request corrections**, enter “Please confirm the declared amount against page 1 of the supporting PDF.” and click **Record action**. Say: “The officer can ask for corrections with a recorded reason. The institution then corrects and resubmits.” Do not falsely accept mismatched evidence for a clean story.

For the main scene:

1. Click **Institutions**.
2. Open the institution A entry (the demo institution's visible name may include Fictional Technical Institute A).
3. Find obligation **PS3-DEMO-A**. Point to required, held, shortfall, term and findings.
4. Do not edit proof receipts or rule values during this short scene.

Say: “We also track the amount the institution is required to maintain. This view compares the requirement with recorded holdings and highlights shortfalls or gaps in the term. The rule configuration shown here is a draft demonstration, not a certified regulatory determination.”

## Scene 4 — release request, every step explained (90 seconds)

Sign out; sign in as **institution_a**. Records → search `PS7-RELEASE-READY` → open → **Request release**.

Say: “For the release example, we use an existing accepted sample whose term has already ended. Release is a separate process with declarations, supporting documents, clearances, and an independent decision.”

### Step 1: Path

- Leave **Path = Term complete**. Do not pick merger, closure or conversion: those require different evidence.
- In **Reason**, enter: `The synthetic deposit term has ended. Please review this request for release.`
- Click **Next**.

Say: “First, the institution explains why it is requesting release. Here, the recorded deposit term has ended.”

### Step 2: Declarations

Each dropdown begins at **Not answered**. For this synthetic clean-case story select **Yes** for ALL SIX statements:

| Visible statement, abbreviated | Answer |
|---|---|
| No dispute among trustees or members | Yes |
| No pending financial embezzlement case | Yes |
| No pending complaint | Yes |
| No pending disciplinary or legal proceedings | Yes |
| Student/staff dues settled and applicable refunds made | Yes |
| Information and documents are true and complete | Yes |

These are favorable statements: “Yes” to “no pending complaint” means there is no complaint. It does not mean a complaint exists. Read each one before selecting it. This is a synthetic scenario only; never choose all Yes blindly for a real case.

- After all six answers, click **Next**.

Say: “The institution records six declarations. These cover disputes, complaints, proceedings, dues, and the completeness of the application. These answers are submitted claims for human review.”

### Step 3: Documents

- Read the checklist. For the seeded sample, required entries should say **uploaded and parsed**.
- Typical term-complete FDR checklist: request letter, Affidavit-6, latest approval letter and FDR. Follow the actual displayed checklist.
- You do not upload from this step. If missing, click **record page** in the warning → **Upload release document** → select the correct category → **Select PDF → Record action**; return and reload the request. Use only documents intended for that category. Do not re-label an unrelated PDF to force a pass.
- If every required item is ready, click **Next**.

Say: “The application checks whether the required document categories are present and readable. A parsed PDF is still subject to officer review; parsing alone does not prove its contents.”

### Step 4: Review

- Check the path and reason.
- Click **Submit release request** once.
- Wait for **Release case [number]**. Write down the case number or copy its URL privately. This is the same case all remaining roles must use.

Say: “Submitting creates a release case. It does not release the deposit. The clearance units and authority still have separate responsibilities.”

## Scene 5 — three independent clearances (45–60 seconds after editing)

For EACH account below: Account menu → Sign out → sign in → **Clearance work**. Use the row with your case number. Do not clear an unrelated row.

| Account | Reason | Reviewed evidence reference |
|---|---|---|
| clearance_pgrc | Synthetic PGRC records reviewed; no objection recorded for this demo. | PGRC/2026/VIDEO01 |
| clearance_vigilance | Synthetic vigilance review completed; no objection recorded for this demo. | VIG/2026/VIDEO01 |
| clearance_grants | Synthetic grants review completed; no outstanding grant issue recorded for this demo. | GRANTS/2026/VIDEO01 |

Enter the **Reason** and **Reviewed evidence reference** fields, then click **cleared** on the correct case row. Both fields must be filled for the button to work. A reference is a synthetic file identifier in this demo, not an actual uploaded clearance certificate. Do not click **hold** or **objection** in the successful release story.

Say during the first unit: “Each unit records its own clearance, reason, and evidence reference. One user cannot stand in for all three units.”

During the remaining two use short cuts and say: “Vigilance and Grants complete their own reviews as well.”

## Scene 6 — officer checklist (25 seconds)

Sign in as **officer → Release cases → Case [your number]**.

- Check the protected documents and the three saved clearances.
- In **Reason / completion notes**, type: `Reviewed the synthetic release checklist, supporting documents and clearance records. No penalty applies in this demonstration.`
- Click **Record officer checklist and penalty review complete**.
- Leave **Reviewed penalty base (INR)** blank and do NOT click **Propose penalty for review** for this clean-case story.

Say: “The officer completes the document checklist and penalty review. No penalty is proposed for this sample. The authority will make the separate authorization decision.”

## Scene 7 — authority, AI assistance and authorization (60 seconds)

Sign in as **authority → Release cases → Case [your number]**.

1. Show the saved clearances and readiness message. Readiness alone is not approval.
2. Optional: click **Generate AI summary** only if it is available and you have rehearsed a working provider call. Allow up to the configured timeout; cut waiting from the video. If unavailable, show the fallback without repeating requests.
3. Say: “AI can summarize recorded facts and highlight risks. Its output is advisory. It cannot approve this request or change the case.” If no result, say: “AI is currently unavailable; the manual review process continues.” Never claim an actual model call passed when it did not.
4. Enter **Reason / completion notes**: `Independently reviewed the synthetic case, supporting checklist and all three clearances. Release authorized for this demonstration.`
5. Click **Record authority authorization** once.
6. Show **APPROVED**, with monitoring still **Active**.

Say: “The authority authorizes the release after independent review. Notice that approval does not end monitoring: completion still needs evidence.”

## Scene 8 — letter, public verification and separate completion (60 seconds)

Remain as authority on the same case.

1. The reason box clears after each successful action. Enter a NEW reason: `Generate the unsigned synthetic release letter after authorization.`
2. Click **Generate unsigned demo letter**.
3. Click **Download protected letter**. Open the downloaded PDF in a new browser tab or PDF viewer. This is the one intentional tab/application switch in this scene.
4. Show its serial and QR. If the PDF exposes a clickable verification link, open it. Otherwise decode the QR during rehearsal and bookmark the exact returned URL. Do not type `/verify/` with a guessed token. Keep this optional if QR handling is awkward.
5. Public verification shows only minimal letter identity and status. Say: “The letter can be checked through its QR-linked record. This demonstration letter is unsigned; it is not a production digital signature.”
6. Return to the original case tab. For an FDR sample there is no RTGS refund-reference input.
7. Enter **Reason / completion notes**: `Manually reviewed the attached synthetic handover evidence and recorded completion.`
8. At **New completion PDF**, select `fixtures/release-evidence.pdf`.
9. Click **Record evidence-backed completion** once.
10. Show **COMPLETED** and monitoring ended; scroll to recorded history.

Say: “Completion is a separate action with new supporting evidence. Only now is the deposit no longer monitored as current. The portal records the evidence and decision history; it does not execute a bank payment.”

## Scene 9 — reports and measured KPIs (40 seconds)

Sign in as **officer → Reports**. Select **Upcoming maturities**, wait, click **Download XLSX**. Optionally select **Released register** to show completed records, without quoting unverified row counts.

Say: “Staff can export the records they are allowed to see. Each report also states its source limitations.”

Click **Process KPIs**. In **From**, choose 1 September 2025 at 00:00. In **Through**, choose 1 October 2026 at 00:00. Click **Measure selected window**. These are date-and-time fields, not plain dates; use the browser picker if typing is difficult.

Say: “These indicators are calculated from recorded events, including turnaround and correction cycles. They are measurements on synthetic history, not a claim that we have already improved a real department's performance.”

## Scene 10 — auditor and institution separation (45 seconds)

Sign in as **auditor**. Open its audit screen from the left menu. Inspect the audit-trail and access-log tabs. Use the integrity-check tab if available and rehearsed; state the actual result. Do not alter database rows to stage a failure.

Say: “Auditors can inspect workflow events and access records. This helps show who did what and which documents were accessed.”

Before leaving, keep a direct URL for institution A's record, for example the inspected sample `/records/44` (verify the actual ID in your environment).

Sign out → sign in as **institution_b → Records**. Show its own institution's records. Optionally paste the A record URL; expect an unavailable/not-found response. If it unexpectedly displays A's private record, stop the demonstration and report a defect.

Say: “Institutions only see their own records. Changing the URL does not grant access to another institution's documents.”

## Closing line

“Pramaan connects deposits, documents, maturity tracking and controlled release in one traceable workflow. Our next step is validating it with authorized real-world users and approved policy data.”

## If a button is disabled or a screen fails

| Symptom | What to do |
|---|---|
| Request release missing | Use institution_a and the accepted current PS7 sample. Check whether a case already exists; then use Open release case instead. |
| Next disabled on Path | Fill Reason. |
| Next disabled on Declarations | Answer all six; none may remain Not answered. |
| Next disabled on Documents | Read the displayed missing/parse/term warning; fix the source document, then reload. |
| Clearance cleared disabled | Fill both reason and evidence reference; ensure it is an OPEN task for that unit. |
| Authority authorization missing | Check three clearances, officer checklist/penalty review, correct authority role and fresh saved state. |
| Letter button missing | Authorization must have succeeded first. If a letter already exists use Download protected letter. |
| Completion disabled | Fill a fresh reason and select a new PDF. |
| Record changed / conflict | Reload, inspect saved state, then decide whether another action is necessary. Do not keep clicking. |
| AI fails | Continue the manual flow. Do not invent or paste a fake output as a live result. |
| Login fails | Verify username separately from password; do not keep guessing and trigger lockout. |

## Five-minute cut

Use the same exact steps but omit new-deposit creation, KPI inputs, public QR tab and B access test. Allocate: intro/dashboard 30s; record/PDF 30s; officer obligation 25s; four release steps 60s; three clearance cuts 35s; officer checklist 20s; authority/letter/completion 65s; reports/auditor/closing 35s. Rehearse first: five minutes is tight with all roles. Do not speed-click faster than saved responses arrive.

## Rehearsal sign-off

- [ ] Each role signs in with the local credential file.
- [ ] PDF viewer and file picker work in the recording browser.
- [ ] PS7 sample has Request release, or its current saved case is clearly identified.
- [ ] Four-step form reaches Documents with every required item ready.
- [ ] Exact same case is used for three unit clearances, officer review and authority action.
- [ ] Downloaded letter opens; optional QR URL was checked.
- [ ] Completion PDF exists and its contents were inspected.
- [ ] Private keys, password files and desktop notifications stay outside the recording.
- [ ] Narration distinguishes synthetic data, draft rules, advisory AI and unsigned letters.
- [ ] Any action performed during rehearsal is accounted for in the next take.
