# Improvement backlog: MVP → stronger hackathon entry → production

This is a broad, prioritized catalog of plausible improvements, **not implemented functionality**, not a commitment to build all of them, and not a guarantee of winning. Select work using the next-steps plan and the team's available time. Preserve the existing tested lifecycle instead of replacing the architecture without evidence.

## How to choose

For each candidate ask: which reviewer/institution problem improves; what evidence supports that need; how will we measure benefit; what can go wrong; can we finish and test it before presentation; what is the fallback? Prefer one complete evidence-backed slice to many unconnected screens.

Priority labels: **P0** = close current sign-off/defect gaps; **P1** = candidate hackathon differentiator after user/data validation; **P2** = useful follow-on; **Production** = necessary for the relevant real/shared deployment, not a claim that the local demo already has it. Effort depends on data/integration access; validate estimates with a short spike rather than promising hours from this list.

## A. Trustworthy review and verification

| Candidate | Priority / why | Evidence required before calling it successful |
|---|---|---|
| Finish target browser/PDF/disconnected rehearsal | P0; closes current unverified manual gates | Actual machine/browser test record; readable PDFs and complete disconnected journey |
| Richer synthetic FDR examples with issuer/reference/amount/dates | P1; existing placeholder PDFs are too thin to prove realistic review | Clear generated provenance, expected fields/pages and independent label check |
| Structured declared-versus-observed comparisons | P1; makes manual scrutiny easier to inspect and evaluate | Reviewer task study; correctly linked field/value/page; old observations preserved |
| Evidence navigation to the relevant document/page | P1; reduces searching and ambiguity | Target viewer behavior and reviewer-time/error measurement; safe fallback download |
| Explicit unknown/unreadable/unsupported outcomes | P1; avoids a misleading apparent pass | Corpus tests and UI that distinguishes incomplete review from confirmed correctness |
| Bounded PDF readability validation | P1 if intake expands; closes known marker-only limitation | Malformed/encrypted/resource-limit tests; safe errors; no authenticity claim |
| Text extraction pilot for text PDFs | P1 only if useful on samples | Held-out per-field accuracy, evidence mapping and manual correction path |
| OCR pilot for scanned/rotated documents | P2 until the corpus shows need | Measured extraction and failure behavior on varied scans; resource/time limits |
| Cross-document field consistency | P1 only for a validated multi-document use case | Authorized expected document set, field provenance and ambiguity/false-positive analysis |
| Versioned reviewed business-rule catalog | P1 only with authoritative inputs | Rule source/date/owner, testable conditions and explicit non-applicability/uncertainty |
| Review checklist tailored to the actual officer task | P1; practical benefit without mandatory AI | User validation, completion/error tracking, no implied regulatory sufficiency |
| Separation of institution declarations, extracted proposals and confirmed facts | P1; prevents trust confusion | UI/data lineage and tests proving unconfirmed data cannot become verified silently |
| Duplicate review context without privacy leakage | P2; current warning intentionally exposes no matching record IDs | Role-specific need, same-institution boundaries and leakage tests |
| Fuzzy duplicate detection | P2; could catch variants but increases false positives | Clearly labeled advisory output, representative labels, precision/recall and human override |

## B. User experience and lifecycle completeness

| Candidate | Priority / why | Acceptance evidence |
|---|---|---|
| Evidence-first detail layout and clearer primary action | P1 after observation; current page is long | Users can locate issue/source/action reliably at intended screen resolution |
| Accessible keyboard/focus, labels and error summaries | P0 for observed blockers; P1 improvement otherwise | Manual keyboard/zoom/screen-reader checks and appropriate automated checks |
| Mobile/small-screen table and form usability | P2 unless target users need it now | No unreachable controls/content at tested widths |
| Search/filter by reference, institution and relevant state | P2; useful if record volume warrants it | Scope-first query handling, empty/error states, representative task timing |
| Clearer correction progress and next responsible actor | P1 if reviewer/institution confusion is observed | State/role-specific labels with no unsupported workflow steps |
| Renewal proposal cancellation/restart | P2; current one-retained-successor restriction is deliberate | Defined lifecycle/history semantics and conflict/monitoring tests |
| Release request withdrawal/rework | P2 only after policy/process agreement | No erasure of prior decisions; role/version/conflict checks |
| Institution-side document checklist | P1 if missing evidence is a frequent problem | Real expected document requirements and improved completion on the same task |
| Meaningful empty/loading/error experiences | P1 for observed confusion | Common failures remain understandable without exposing sensitive diagnostics |
| Bulk actions | P2; potentially consequential | Explicit permissions, per-record results, transaction/replay safety and human confirmation |

Do not add charts, animations, a separate frontend framework or extra status cards merely to look more advanced. UI work should remove observed confusion or strengthen the demo story.

## C. Evaluation and impact evidence

| Candidate | Priority / why | Acceptance evidence |
|---|---|---|
| Independent ground-truth review | P1; author-reviewed boundary labels are limited | Second-reviewer adjudication, uncertain cases recorded, provenance retained |
| Held-out representative document set | P1 before extraction claims | Development/evaluation split with no test-set leakage or retrospective label adjustment |
| Manual baseline versus assisted workflow study | P1; measures actual user value | Same task definition, measured times/errors/sample size, limitations reported |
| Field-level extraction metrics and unsupported-rate reporting | P1 only if extractor exists | Precision/recall/FP/FN and evidence alignment, not one inflated overall accuracy score |
| Reviewer correction/override measurement | P1 if assistance is added | Ability to recover from a wrong suggestion and inspect its evidence |
| Load and concurrent-writer tests | P2 / Production depending on target | Reproducible volume, latency distribution, conflicts, database behavior and limits |
| Stability and failure-injection coverage | P1 for new integrations/storage behavior | Timeout, disk, database, retry/replay and no-corruption cases |
| Regression benchmark history | P2; prevents silent quality regression | Versioned datasets/rules/results and repeatable commands; no overwriting old evidence |

Do not reuse the existing perfect boundary-set result as an OCR, bank-authentication, regulatory or population-level accuracy claim. No manual-time saving percentage has yet been measured.

## D. Authorized integrations and automation

| Candidate | Priority / dependency | Acceptance evidence |
|---|---|---|
| Due-action reminder delivery | P2; agree recipients/channel first | Idempotent schedule, delivery/failure audit, privacy, timezone and manual fallback |
| Escalation/task assignment | P2; needs owner/process definition | Who is responsible and when, with reasoned state transitions and no fabricated policy |
| Authorized bank-issued verification mechanism | Depends on formal access; potentially high value | Real authorized endpoint/data provenance, verified versus submitted separation, outage/rate-limit behavior |
| AICTE-system integration | Depends on authorization, schema and access | Defined authoritative data ownership, minimal duplication and auditable failure handling |
| External extraction/LLM service | Optional; never mandatory just for an AI label | Measured benefit, privacy/cost limits, evidence references, prompt-injection defenses and safe manual/offline fallback |
| Background processing | P2 only when actual long-running work exists | Durable jobs, status/failure visibility, bounded retries and idempotent writes |

The current system has none of these runtime connectors or delivery workers. A simulation must stay labeled simulation and must not populate a “bank verified” status as though an authorized source confirmed it.

## E. Security, reliability and production operations

| Candidate | Priority / purpose | Acceptance evidence |
|---|---|---|
| Production server, TLS, secure cookies, secret management | Production before public exposure | Verified target configuration, deployment checks, static/private-file serving and recovery |
| Individual accounts, login throttling and appropriate MFA | Production / shared access | No shared demo passwords, account provisioning/revocation and abuse tests |
| Upload isolation/scanning and request/resource limits | Production before untrusted documents | Malicious/malformed corpus, size/time limits and safe quarantine/manual states |
| Encryption/ACL/retention for files, database and backups | Production before sensitive data | Threat/data model, key/access ownership, deletion/retention and restore checks |
| Tamper-evident audit and administrative-access controls | Production where required | Threat model, restricted privileged writes and verifiable retention/integrity behavior |
| Crash reconciliation between files and database | P2 / Production | Orphan/missing/corrupt-file detection and operator-safe repair with tests |
| Central operational logs with redaction/retention | Production | Useful diagnosis without SQL/document contents/secrets, controlled access and alert tests |
| Automated private backup and disaster recovery | Production | Defined objectives, off-machine protection and timed restore rehearsal |
| Database scaling/indexing and pagination | P2 / Production only after measurements | Realistic workload evidence; normalized duplicate checks/queries preserve semantics |
| Strong dependency/hash provenance and recurring advisory review | P2 / Production | Reviewed pins/hashes, reproducible package and tested update policy |
| CI with tests/migration/evaluation gates | P1 for team collaboration | Clean pipeline without credentials/runtime data; reproducible results and artifacts |
| Container/deployment automation | P2 / Production if team benefits | Fresh reproducible target and private data boundaries; not added as decorative infrastructure |

## F. Stronger judging demonstration and handover

- P1: one compelling end-to-end story centered on a reviewer problem, with a clear evidence trail and human decision.
- P1: explain innovation as measurable reduction in ambiguity/effort and traceable lifecycle, rather than merely attaching a chatbot.
- P1: show one successful case, one discrepancy, one unsupported case and one unauthorized attempt.
- P1: record actual setup/evaluation/recovery evidence and answer likely questions about trust, data and limitations.
- P1: keep a working disconnected fallback, readable architecture diagram and short user/operator guide.
- P2: obtain structured usability feedback from intended users and a short authorized pilot report.

## Recommended shortlist

First finish manual sign-off. Then validate a richer document-review use case, build an independently checked synthetic corpus, and choose structured evidence comparison/navigation as the smallest likely differentiator. Pilot extraction only if it measurably improves that task. Production hardening is a separate release target.

Choose at most one or two new slices for the next iteration and write their acceptance tests before broad changes. A stable, honest, well-demonstrated system with measured value is a stronger entry than a larger system whose verification claims cannot be defended.
