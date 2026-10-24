# S2 unresolved policy decisions

Status: OPEN DECISION LOG, not approved AICTE policy. Prepared 24 October 2026.
No approvals, legal interpretations or team agreements are recorded as completed.
This document changes no rule, calculation, permission, schema or workflow.

The draft source and point-in-time checks are recorded in [S2.md](S2.md).
Current addenda, applicability and case interpretation still need confirmation.
The team may use explicitly provisional choices with synthetic data; that does
not make them safe for real cases. No automatic penalty, exemption, term extension,
withdrawal or release may be inferred from the calculator.

## Open decisions

| ID | Topic | Current local behaviour | Evidence/decision needed | Impact while open |
|---|---|---|---|---|
| P-01 | Authoritative rule edition and effective dates | Explicit caller-selected rule snapshot; all catalogue payloads are DRAFT_DEMO_NOT_APPROVED; seed window is a supplied demo date | Confirm applicable APH edition, addenda/corrigenda, source hierarchy and approval-cycle dates with the policy owner | No published/current-policy claim or default production rule selection |
| P-02 | Exempt institutions and programmes | No automatic exemption for GOVERNMENT, AIDED or UNIVERSITY; model exemption metadata does not itself authorize exemption | Confirm entity categories, relevant age/recognition dates, new-programme exceptions, earlier NOC evidence, required approver and documents | Do not infer exemption from one profile type or unknown age; mark applicability unresolved |
| P-03 | Conversion balances and historical deposits | Calculator reports gross requirement; it does not subtract previously deposited money or assign legacy holdings | Decide eligible prior amounts, programme overlap, earlier releases/refunds, interest treatment, verification threshold and how converted institutions retain the original term | Do not manufacture net requirement or count an instrument twice; reviewed adapter/backfill required |
| P-04 | Leased land/building multiplier | PRIVATE input with either asset LEASED doubles the aggregate once | Confirm whether private describes the institution or leased ownership, treatment of mixed programme premises, changed tenure and conversions | Demo convention only; no automatic application to a real institution |
| P-05 | Term origin and leap-day anniversaries | Explicit term start plus configured years; February 29 maps to February 28 when needed | Confirm LoA date vs payment/deposit date, remaining legacy term, renewal continuity, inclusive end and leap-day anniversary | No auto-population of S1 terms or reset of obligation duration on renewal |
| P-06 | Maturity-day coverage and bank timing | Date-only issue/maturity boundaries are inclusive | Confirm same-day bank discharge/renewal timing, non-working days and any handover gap | Current date model is a synthetic convention, not bank settlement proof |
| P-07 | Coverage definition and obligation end | Current accepted/non-superseded/non-released snapshots; first gap stops continuous coverage; gap_days is remaining term from that break | Confirm continuous vs accumulated gap reporting, acceptable future holdings, how obligations remain due while release is pending, and post-term shortfall treatment | Do not present as historical reconstruction or automatically release at term end |
| P-08 | Penalty base and rounding | Integer paise; half-up rounding to a paise; proposal requires human confirmation | Confirm applicable base (required deposit vs FDR principal), whole-rupee/paise rounding, compounding/caps and overlapping penalty precedence | Proposals only; no assessment ledger, debit or automatic deduction |
| P-09 | Late proof, cutoffs and cross-year cases | Both proof and Affidavit-3 receipts needed; 15-day inclusive grace; draft 2.25(f) bands; late cross-year calculations rejected; post-July returns authority-review outcome | Confirm receipt vs document dates, partial/late submission, calendar vs approval cycle, governing clause where instruments differ, cutoff/grace priority and required human action | No extrapolated rate, withdrawal or automatic sanction; unsupported cases stay for review |
| P-10 | Rule publication and exemption decision powers | Seed is unapproved; snapshots are frozen; underlying S1 RuleSet rows are editable storage | Agree maker/checker roles, distinct identities, immutable publication boundary, audit records, version fields and supersession/effective-window rules with team and policy owner | Do not treat approved_by storage or role labels as an implemented publication service |
| P-11 | Reminder/escalation clocks | Typed team-proposed thresholds and symbolic recipients; no scheduler or delivery | Confirm recipients, holiday calendar, working/calendar-day definitions, day-zero convention and SLA priorities | K6 must not label a console/demo action as delivered notification or a proposed SLA as statutory |
| P-12 | Release-path requirements | Draft schema retains mandatory documents, three clearance symbols and conditional requirements; no case workflow is implemented here | Confirm path conditions, conditional certificate exceptions, external-NOC holds, authority/signatory, document types and latest letter templates | S2 configuration is not an S5 clearance or release decision |
| P-13 | Unknown and legacy data | Null requirement/term remains unknown; missing adapter raises explicit input error; empty findings do not mean compliant | Agree how unknown applicability, unsupported cells, incomplete mapping and unconfirmed holdings appear in API assessments | No invented zero requirement, clean validation badge or independent confirmation |

Saksham owns translating confirmed decisions into versioned configuration and
tests. Kushagra owns shared authentication/role/error and scheduling foundations;
Yash owns instrument/verification integration. These ownership notes do not
constitute an agreement or notification to either teammate. Domain authority
approval must come from the appropriate human/policy owner, not an AI assertion.

## How a decision becomes implementable

For each decision, record: ID, dated source and clause, exact question and selected
interpretation, applicable institution/case/cycle, named human decision-maker,
approval date, examples and boundary outcomes, effective interval, affected rule
version and migration/audit implications. Until that record exists, status stays
OPEN. No decision above has been resolved by this document.

After approval, create a new appropriate rule/schema version and add literal
expected cases. Preserve prior rule payloads, fingerprints, obligation snapshots
and evaluation reports. Never edit frozen labels merely to accept the current
implementation's output. A schema change that alters required release semantics
needs an explicit schema revision; changing a numeric draft threshold alone is
not authorization to weaken those requirements.

## Independent work vs integration blockers

Documentation and technical error/boundary fixes can continue locally. K1/Y1
integration is needed for secure persisted APIs and complete holding assessment.
The policy questions do not authorize adding new K1/K4/K6 functionality or S3.
Real-data use remains blocked while applicable decisions lack confirmation.
