# Semifinal synthetic extraction evaluation

Date: 27 October 2026. All documents are invented synthetic test fixtures; no applicant data was used. Live transfer of these PDFs was explicitly authorized by Saksham. Provider requests used the existing private environment configuration; no credentials are stored here.

Corpus: twelve PDFs / 72 field slots, of which 63 contain an expected value. Four cases were assigned to the held-out subset before evaluation. Labels are author-supplied and mechanically validated, with rendered-page inspection. **Independent human ground-truth sign-off remains outstanding.** The corpus is too small and artificial for real-world or regulatory accuracy claims.

## Results

| Measure | Live configured AI | Offline PDF-text baseline | Local OCR |
|---|---:|---:|---|
| Successful service responses | 10/12 | 12/12 | 0/12 |
| Exact and supported documents, with successful response | 10/12 | 9/12 | Not available |
| Correct non-null predictions | 58/58 | 45/45 | No predictions |
| Recall against 63 expected values | 58/63 (92.06%) | 45/63 (71.43%) | Not an OCR accuracy measurement |
| Exact field slots, including unknown labels and failures | 60/72 (83.33%) | 54/72 (75%) | 0/72, engine unavailable |
| Correct supporting pages among predictions | 58/58 | 45/45 | Undefined |
| Mismatch TP / FP / FN | 3 / 0 / 0 | 3 / 0 / 0 | No product mismatch findings |
| Mismatch precision / recall | 100% / 100%, on 3 labelled flags | 100% / 100%, on 3 labelled flags | Not applicable |
| Wrong / invented / omitted expected values | 0 / 0 / 5 | 0 / 0 / 18 | All expected values unavailable |

The live AI run processed T01–U01 successfully. U02 (conflicting values) and U03 (unreadable scan) returned unavailable because the existing ten-attempt hourly limit was reached. Their provider accuracy was **not measured**. Five expected U02 values remain false negatives in aggregate field recall. Do not describe this as twelve successfully extracted documents or proof of correct abstention on those two samples.

The text baseline's three image-only scans produce no field values; this is its expected limitation. Its mismatch comparisons are deterministic offline comparisons, not AI inference. Local OCR could not run because Tesseract was not installed/configured. Its unavailable responses verify the fallback boundary, not OCR quality.

Live median end-to-end duration was 2,414 ms, with observed range 16–3,078 ms across all attempts, including immediate rate-limit rejections. These are a single sequential synthetic run, not throughput, production latency or a statistical service guarantee. Per-document durations, actual answered model identities and per-field results are in the JSON report.

## Scoring rules

- Money is compared numerically; other field strings are stripped and case-folded. Dates must already satisfy the service's ISO-date schema.
- A wrong non-null value is a wrong prediction and a missed expected value. Unknown/absent fields must not be invented.
- Supporting pages must match the labelled page. A value without a supporting page is rejected by the extraction service.
- Unavailable responses earn no exact-match credit, even for null labels. They stay in aggregate denominators. A successful unknown-field response is an abstention, distinct from an unavailable service.
- Precision is undefined when there are no predictions; JSON uses null. Mismatch metrics count labelled field-level findings, not entire applications.
- The actual report is based on raw stored `AiRun.output` fields. For the final per-field expansion, mismatch comparisons were replayed from those fields against declared values using the same deterministic comparison; no new provider calls or fabricated responses were used.

## Diagnostic run and verified fix

`semifinal-ai-initial-results.json` retains the first diagnostic measurement. Running OCR and AI concurrently exposed a pre-existing defect: the extraction quota query counted other AI operations, including failed LOCAL_OCR runs. That diagnostic run was not a valid final benchmark and predates the final failure-scoring adjustment. Do not quote its accuracy.

The extraction quota now selects DOCUMENT_EXTRACTION only, with a regression test. The final live run used a fresh, separate synthetic evaluation database; the normal quota remained enabled. No log deletion, account creation to evade quota, provider-output changes or increased limits were used to produce the final run.

## Reproduction and next verification

Follow `docs/owned/SEMIFINAL_UPGRADE.md` for manifest validation, isolated seeding and exact evaluation commands. Repeated live runs consume quota and may be rejected until its window expires. Preserve each raw report rather than overwriting inconvenient failures. Test U02/U03 after the legitimate quota window expires, and obtain independent label review before broadening accuracy claims.

The local audit, notification and browser measurements are release checks, not AI extraction accuracy. See the companion semifinal results document for those outcomes.
