# Requirements: what problem we agreed to solve

## 1. Starting problem

The supplied SIH statement concerns AICTE security-deposit / Fixed Deposit Receipt administration: institution-wise records, supporting documents, scrutiny, maturity/renewal tracking, release/refund requests, visibility, access control and history. The supplied statement is preserved in [original-problem-statement.txt](original-problem-statement.txt). It is project input, not evidence that any particular current AICTE regulation has been independently checked.

The general phrase “AICTE application validation” appeared in the planning conversation. The actual implemented domain is **FDR instruments**, not all application documents, courses, approvals or regulatory criteria. There is no Application model or approved regulatory rule corpus.

## 2. Users and the work they need to do

| Person | Need | Current route through the product |
|---|---|---|
| Institution submitter | Enter deposit details, send PDFs, correct errors, request renewal/release | Own register → draft/detail → submission/correction/linked renewal/release request |
| Reviewing officer | Inspect available evidence, record findings and reasons, decide whether to accept for tracking | Submitted queue → document download → observation/resolution → decision |
| Competent authority role | Independently assess release and record completion evidence | Release queue → authorize/reject → separate completion action |
| Trusted local operator | Install, seed, inspect due actions, verify and recover | Setup/management commands, verification scripts and private data backup |

The prototype's group names are Institution, Officer and Authority. Institution A/B are fictional seed entities, not real institutions or AICTE accounts.

## 3. Why the MVP was deliberately narrower

The target was a working 48-hour hackathon prototype, initially built by one developer. We did not have authorized bank APIs, AICTE production access, real applicant records, a validated regulatory rule set or an OCR ground-truth corpus. The design therefore favored a complete human-reviewed lifecycle with explicit trust boundaries over unsupported automated verification claims.

The key choices were one Django application, server-rendered forms, local SQLite/files, deterministic checks, manual evidence references and no mandatory external runtime service. This reduced setup/integration costs and made a local demonstration reproducible. It did not eliminate the need for later user validation or production hardening.

## 4. Requirement-to-implementation matrix

| Requirement from supplied problem | Approved MVP interpretation | Actual status / boundary |
|---|---|---|
| Centralized institution/instrument repository | One owner-scoped instrument record with bank, reference, INR amount, issue/maturity dates and review status | Implemented; no general application dossier |
| Digital document management | Protected PDF upload/download and preservation of older uploads | Implemented envelope validation; no parsing, malware scan or authenticity proof |
| Verification and discrepancy detection | Required fields/date/amount validation; missing FDR metadata; duplicate heuristic; human document observations | Implemented; automatic PDF value comparison and authorized-source verification absent |
| Distinguish submitted from independently verified information | Always label bank verification as unconfirmed; treat acceptance as administrative tracking | Implemented explicit disclaimers; no confirmed-bank state fabricated |
| Validity/maturity monitoring | Accepted-current dashboard subsets and read-only report with 30/15/7 configurable demo thresholds | Implemented; thresholds are demonstration settings, not asserted regulatory policy |
| Renewal/replacement tracking | One linked successor proposal; acceptance supersedes old record and preserves history | Implemented linear lineage; no cancellation/branching |
| Release/refund workflow | Request, independent authority decision and separate evidence-backed completion | Administrative recording implemented; eligibility determination and financial execution absent |
| Alerts/escalations | Surface upcoming/today/matured records and print due-action report | Views/report implemented; delivery, scheduler and escalation absent |
| Dashboard/reporting | Six scoped categories, filtered lists, CSV matching the current view | Implemented; no custom analytics/search engine |
| Audit and access control | Roles, institution boundaries, reasoned events, optimistic versions and protected files | Implemented through supported application paths; no tamper-proof audit infrastructure |
| Integration/data security | No unsupported integration claims; safe local synthetic demonstration | External integration, TLS production hosting, encryption/retention and real-data governance deferred |
| Measurable improvement | Reproducible functional tests and bounded technical-rule evaluation | Measured narrow results available; manual-time savings/real operational impact not measured |

## 5. Approved implementation milestones and exit criteria

1. **Smallest vertical slice:** institution can create/upload/submit; officer can request correction/accept; institution sees final status and retained history. Other institutions cannot read the record/PDF.
2. **Scrutiny:** named findings are explainable; manual observation references the correct document and optional positive page; blocking observation requires explicit resolution.
3. **Maturity:** cards/lists/report use the same definitions and scope; threshold boundaries work; reports do not write workflow state or send notifications.
4. **Renewal:** original remains current until linked successor acceptance; only one successor; atomic supersession; preserved PDFs/history and no private-draft leakage.
5. **Release:** requester cannot authorize their own request; authorization is not completion; new evidence and explanation required for completion; monitoring changes only then.
6. **Final demonstration:** CSV respects scope/filters and spreadsheet protection; fresh offline dependencies/scenarios work; tests/recovery/limitations are documented.

Current release sign-off additionally requires the target browser/PDF/offline manual checks. Code written, tests passed and target demo approved are separate statements.

## 6. Facts, assumptions and proposals

**Facts in code:** data is in local SQLite/files; PDFs have UUID-based storage names; roles fail closed when absent/ambiguous; record versions protect against stale changes; findings use technical-v2; dates are calculated at read time.

**Demo assumptions:** users are trusted local operators using synthetic records; Python 3.12 is installed; the filesystem is writable; generated passwords are kept private; human officers interpret documents honestly; one retained successor is adequate for the demonstration.

**Not established:** regulatory sufficiency of any deposit, legal eligibility for release, bank authenticity, accuracy of manual observations, representative real-document accuracy, production availability/security, or an externally reviewed UI/accessibility standard.

**Future proposals:** structured field comparisons, better evidence navigation, a representative expert-reviewed corpus, extraction pilots, useful policy checks, notification delivery and integrations. See [next steps](../next-steps.md) before implementing them.

## 7. What a teammate must not accidentally change

- Do not equate ACCEPTED with authenticated, compliant or financially settled.
- Do not remove an instrument from monitoring merely because release was authorized.
- Do not overwrite the previous PDF, observation or audit entry during correction.
- Do not resolve a blocking observation automatically because someone edited an amount.
- Do not expose a private draft to staff or another institution's record in an export.
- Do not infer bank confirmations, old lineages or release decisions when migrating existing records.
- Do not turn optional external services into mandatory demo dependencies without a tested failure path.
