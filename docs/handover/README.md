# Teammate handover: start here

This folder is the replacement for needing to read the previous developer's chat history. It explains what exists, why it exists, how to run/test it and what should happen next. No prior Django knowledge is assumed.

## Suggested reading path

1. Read the root [README](../../README.md). Clone the actual GitHub repository and get an untouched copy running before editing.
2. Read [requirements and scope](completed/requirements-and-scope.md). Understand that this is an FDR lifecycle MVP, not a deployed bank-verification or OCR system.
3. Read [build history](completed/build-history.md). Follow the six milestones and their acceptance gates.
4. Use the [code map](completed/code-map.md) while opening the files in your editor.
5. Follow the [beginner testing walkthrough](testing/README.md). Record observations in a copy of the [test record](testing/test-record-template.md).
6. Review [next steps](next-steps.md) with the team before choosing work. The [improvement backlog](improvements.md) is a menu, not a request to implement everything.
7. Follow the [transfer checklist](transfer-checklist.md) to confirm that the handover is independent of the outgoing developer's machine.
8. Read the team's two planning PDFs, `gap-analysis-and-implementation-plan.pdf` (three-stage priority plan, problem-statement traceability, AICTE APH deposit rules, React + Django API architecture) and `team-task-allocation.pdf` (who builds what, deadlines, dependencies). **They are shared privately and are not in this repository.** Save them in the git-ignored `planning/` folder at the repository root. Everything they mark PROPOSED is not implemented.
9. AI coding agents working for Yash and Saksham must follow [AGENTS.md](../../AGENTS.md).

## What the teammate inherits

- One Django application, an HTML/CSS frontend, SQLite models/migrations and private local PDF storage.
- Real session authentication, role/institution scope, optimistic version checks, database constraints and transactional workflow services.
- Six implemented milestone slices plus release-readiness fixes.
- Three generated PDF fixtures, 17 seeded instruments and four local accounts created by setup.
- 159 tests at the recorded baseline, real HTTP scripts, frozen synthetic evaluation and a clean offline package builder.
- A release report that explicitly leaves target visual/offline rehearsal open and blocks public/real-data deployment.

What does not transfer: a running server, the old developer's browser sessions, virtual environment, local credentials, mutable database, old replay server, cache paths or public hosting. Setup creates the new machine's local state.

## First-day checklist

- [ ] Receive the GitHub repository URL/access and record the handover branch/commit.
- [ ] Install/locate Python 3.12 and open PowerShell in the actual project folder.
- [ ] Set up a fresh copy, run verification and open localhost:8010.
- [ ] Find the four accounts' newly generated credentials locally.
- [ ] Explain the three roles and demonstrate A/B isolation.
- [ ] Show one discrepancy, one renewal lineage and one completed release.
- [ ] Know which behavior is real, which data is synthetic, and which capabilities do not exist.
- [ ] Complete and record the manual release checks on your target machine.
- [ ] Choose one next task, its acceptance test and the files likely to change.

## Vocabulary in plain language

| Word | Meaning here |
|---|---|
| FDR / instrument | One tracked fixed-deposit record and its declared details; not a verified bank asset |
| Institution | The organization that owns a record; A and B are fictional examples |
| Officer | A person who inspects a submission, records observations and accepts/requests correction |
| Authority | A separate role for release authorization/rejection and recorded completion |
| Frontend | Pages/forms you see in the browser; templates plus local CSS |
| Backend | Python code that checks permissions, validates input and changes records |
| Database / migration | Stored metadata / an ordered instruction that creates or changes its structure |
| PDF storage | Original uploaded bytes; distinct from the metadata in SQLite |
| Draft / submitted / accepted | Editable private proposal / awaiting officer / accepted for tracking |
| Observation | A human's document-linked finding; a blocking one requires explicit resolution |
| Superseded | Old accepted instrument replaced by an accepted linked successor |
| Authorized release | Permission recorded, but completion has not yet been evidenced |
| Completed release | Human completion entry plus new evidence PDF; not a payment executed by the portal |
| Test / fixture | An executable expected-behavior check / generated sample input |
| Seed / idempotent | Create sample records / rerunning does not reset existing work |
| Virtual environment | A project-local Python dependency folder, .venv; not portable between machines |
| 400 / 403 / 404 / 409 / 503 | Invalid request / forbidden / hidden or missing / state conflict / temporary operational failure |

## Working agreement

Keep one authoritative development folder and one separate fresh demo clone. Mark every proposed feature as proposed until implemented and tested. Do not describe successful technical checks as bank authenticity, regulatory compliance or AI extraction. Preserve prior documents and history. Do not send local credential files, real records or backups as part of the ordinary handover.

The handover documentation describes source inspection and recorded evidence. It is not a fabricated Git/commit history: no repository/remote was created by this work, and there are no invented commit IDs or historical timestamps.
