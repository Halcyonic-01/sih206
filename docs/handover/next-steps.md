# Next steps: the order the incoming teammate should follow

This is a **future-work plan**, not a list of implemented features or an instruction to begin coding everything. The handover itself changes documentation only. Work on one accepted task at a time; retain the existing lifecycle and require evidence before expanding scope.

## Step 1 — establish ownership and a reproducible baseline

**Why first:** a teammate cannot safely extend a system that only runs on its creator's machine.

1. Complete the transfer checklist; identify the authoritative editable folder.
2. Run fresh setup and the full verification gate before editing.
3. Save repository URL, branch/commit, Python/browser versions and actual results in a private test record.
4. Use the team's actual GitHub repository and agree on branches/reviews; do not invent a remote or assume an old commit history.
5. Keep a separate untouched demo extraction and a private backup of needed local data.

**Read:** root README, code-map.md, release-readiness.md. **Deliverable:** teammate-run baseline and selected source-of-truth location. **Exit gate:** setup works independently; all baseline tests pass or every discrepancy is explained. Do not silently lower expected results.

## Step 2 — close the manual release gates

**Why:** automated HTTP tests do not prove layout, actual PDF viewing or physical offline presentation.

1. Follow the beginner testing walkthrough on the actual presentation machine.
2. Check forms/tables/navigation at intended screen resolution and zoom; test keyboard focus.
3. Download/open the discrepancy PDF and completion evidence; confirm readable contents.
4. Disconnect Wi-Fi/Ethernet/tethering and rehearse fresh installation using locally prepared wheels from a clone and the complete demo.
5. Restart and verify that decisions/documents persist.
6. Record PASS/FAIL and observed errors; keep unresolved failures visible.

**Likely files only if a reproduced defect needs correction:** templates, app.css, related view/form, targeted tests. **Deliverable:** signed target-machine test record. **Exit gate:** no open critical demo-blocking failure; no claim of disconnected or visual verification unless performed. This does not approve real-data/public deployment.

## Step 3 — validate the actual reviewer problem before choosing more features

**Why:** the present MVP proves lifecycle tracking more strongly than verification effectiveness. More screens alone do not close that gap.

1. With authorized stakeholders or an appropriately briefed proxy reviewer, walk through one real administrative process without collecting confidential records unnecessarily.
2. Ask which errors are frequent, what evidence is needed, and which delays a portal can actually reduce.
3. Obtain an authorized sample format or generate a richer synthetic substitute. List the declared fields and expected document evidence explicitly.
4. Distinguish basic completeness, document consistency, regulatory eligibility and bank authenticity; they require different evidence and authority.
5. Agree on one measurable problem, for example omitted amount comparisons or time to locate evidence. Do not claim measured improvement yet.

**Files to update:** requirements-and-scope.md or a new reviewed requirement note, evaluation provenance/labels and test plan. **Deliverable:** one agreed use case with inputs, expected outcomes, known ambiguities and human decision owner. **Exit gate:** team can explain why the next task improves an actual user outcome.

## Step 4 — strengthen the sample corpus and baseline measurement

**Why:** 24 synthetic metadata cases are valuable regression checks, but not a representative bank-document benchmark.

1. Preserve evaluation/cases.json and its before/after evidence; do not overwrite history.
2. Create a separate versioned corpus with legal provenance, synthetic/authorized status, expected values and document/page references.
3. Include clear, incomplete, conflicting, duplicate, rotated/scanned, unreadable, password-protected and multi-page variants where relevant to the chosen use case.
4. Have a second reviewer check labels; mark uncertain cases instead of pretending certainty.
5. Separate development examples from held-out evaluation examples.
6. Record manual review time and errors on a defined task before adding automation, using the same task definition for any later comparison.

**Files:** a new evaluation dataset/version and evaluation tests/tooling, not retroactive relabeling of old results. **Deliverable:** documented provenance, adjudicated labels and measured manual baseline. **Exit gate:** the dataset and metrics correspond to the claim the team intends to make. No invented accuracy/savings numbers.

## Step 5 — choose one verification-focused implementation slice

**Suggested candidate, subject to team agreement:** make document comparison easier to inspect by recording declared value, observed value, field and evidence reference in a structured way. Start human-assisted. The current comment-based observation workflow already supplies the lifecycle and human oversight foundation.

1. Define exactly which fields matter for the agreed use case.
2. Specify the evidence display and allowed reviewer actions before modifying the schema.
3. Identify migration/compatibility implications; existing free-text observations and audit snapshots must remain readable.
4. Add tests for matching/conflicting/unknown values, wrong-document references, authorization, stale updates and audit preservation.
5. Implement the smallest end-to-end path and demonstrate it with held-out examples.
6. Measure the same manual task again and report actual difference and limitations.

**Likely files if approved:** models/new migration, forms, services, detail template, observation tests and evaluation. **Exit gate:** a reviewer can verify the evidence and correct an error; the old 159-test baseline remains protected by relevant regression coverage. Do not start OCR merely to satisfy an AI label.

## Step 6 — improve document intake trust if the next scope includes untrusted files

**Why:** the current marker-only gate accepts an unreadable PDF-shaped body. This is a known limitation, not a completed readability/security feature.

1. Define the supported file class, failure responses, resource limits and what “readable” means.
2. Evaluate a bounded parser/rendering approach against the corpus before changing runtime dependencies.
3. Consider isolation, timeouts, encrypted/unreadable cases and malware handling; basic parsing is not a malware scan.
4. Preserve original bytes and return “needs review/unsupported” rather than inventing content.
5. Test no partial record/file state on parse, storage and timeout failures.

**Deliverable:** a tested, explicitly bounded intake contract. **Exit gate:** unsupported/unreadable cases have safe, explainable handling; neither parser success nor antivirus success is described as authenticity. This work is required before accepting real/untrusted documents, not a reason to broaden the current demo silently.

## Step 7 — consider extraction only after evidence shows a benefit

1. Test simple text extraction on text PDFs before considering OCR for scans.
2. Record per-field outputs, missing/ambiguous values and page evidence; preserve the original document.
3. Use deterministic validation for clear rules. Never infer official policy or bank confirmation from a model response.
4. Evaluate on held-out ground truth, including false positives/negatives and unsupported documents.
5. If any external model/service is proposed, evaluate cost, keys, authorization, privacy, prompt-injection boundaries, timeouts/rate limits and an offline/manual fallback.
6. Require human confirmation before consequential status changes.

**Exit gate:** measured reviewer benefit and acceptable error behavior, not merely a demo that produces text. If the gate fails, keep the human-assisted workflow and report the failed experiment honestly.

## Step 8 — improve the presentation around verified value

1. Choose one story with a clear before/after reviewer task, rather than listing every feature.
2. Improve evidence visibility, terminology and error guidance where manual tests show confusion.
3. Prepare matching/conflicting/unreadable examples, a short architecture explanation and real evaluation results.
4. Rehearse role switches, exports, offline operation and restart/recovery.
5. Keep a fresh seeded fallback and explain preseeded outcomes honestly.

**Files:** templates/CSS only for agreed UI defects/improvements; demo-script.md and verified evidence. **Exit gate:** a teammate can present without the author, within five minutes, without unsupported AI/bank/regulatory claims.

## Step 9 — separate production preparation from the hackathon

If real/shared deployment becomes a goal, first agree on data authorization, operational ownership and release criteria. Address TLS/production serving, secret management, individual accounts/throttling, upload isolation/scanning, encryption/ACL/retention, backups/recovery, audit governance, monitoring, concurrent writes and authorized integrations. The current localhost launch scripts are not deployment scripts.

Do not enable public access by changing a bind address or disabling DEBUG checks. Do not declare regulatory compliance without the relevant authority's validation. The broader backlog is in improvements.md; selecting a production hosting stack now is outside this documentation handover.

## Definition of done for every next task

- [ ] One user need and accepted scope stated.
- [ ] Input/output, trust boundary and failure behavior defined.
- [ ] Meaningful tests demonstrate the new/corrected behavior.
- [ ] Existing workflow, scope, audit and evidence preservation still pass.
- [ ] Evaluation claims match actual data and measurements.
- [ ] Fresh setup/upgrade/recovery implications checked where relevant.
- [ ] Documentation and known limitations updated.
- [ ] Demo and offline fallback still work on the target machine.

## If only one work session remains

Complete Steps 1–2 and rehearse the verified demo. Fix reproduced defects, improve explanation and prepare honest evidence. Do not rush an unevaluated extraction model or unavailable integration into the last hour. Winning is not guaranteed by feature count; demonstrable usefulness and trust matter more.
