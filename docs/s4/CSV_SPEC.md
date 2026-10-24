# S4 institution CSV validation specification

Status: local demo format `institution-csv-v1`, not an agreed external AICTE
schema or API contract. This implements only pure validation and synthetic test
data. S4's reports, KPIs, upload/preview UI, authorized commit, persistence and
audit remain unimplemented.

## Input contract

One row represents one institution identity plus its S1 profile. All ten columns
are required exactly once; order may vary. Header spelling/case/spacing is exact.

| Column | Required value after surrounding whitespace trim | Maximum characters |
|---|---|---:|
| `aicte_id` | ASCII letters/digits, `_` or `-`, starting with letter/digit | 50 |
| `institution_code` | Same demo token syntax | 30 |
| `institution_name` | Nonblank Unicode text | 200 |
| `trust_name` | Nonblank Unicode text | 250 |
| `institution_type` | GOVERNMENT, AIDED, PRIVATE or UNIVERSITY | 20 |
| `region` | Nonblank text; no geographic authority validation | 100 |
| `state` | Nonblank text; no geographic authority validation | 100 |
| `contact_email` | Django's existing email syntax validator; no DNS lookup | 254 |
| `status` | ACTIVE or INACTIVE; no automatic business decision | 10 |
| `data_classification` | Exactly SIMULATED | 9 |

Identity tokens are uppercased after validation, preserving leading zeros. Other
values retain case and internal whitespace. Enum codes must already be uppercase.
This token grammar and normalization are conservative demo choices, not claims
about official AICTE identifiers. Review them against the actual authorized source
and team identity contract before a real adapter or commit service is built.

Use comma-delimited UTF-8, with or without a UTF-8 BOM; LF/CRLF and normal CSV
quoting are supported. No delimiter/encoding guessing, Excel workbooks, comments,
formula evaluation or automatic corrections. Blank records and wrong column counts
are row errors. Blank fields are not defaults. Header-only input is a file error.
Input is capped at 1 MiB and 1,000 data records; these are local demo limits.

Reject Unicode category-C characters (controls, format/bidi/zero-width, surrogates,
private-use and unassigned characters), including tabs/newlines inside fields,
before trimming. Reject trimmed values starting with `=`, `+`, `-` or `@` in any
column; do not silently escape or evaluate spreadsheet formulas. Later CSV exports
must still apply their own output escaping. These checks are not malware scanning.

No programme approvals, obligations, amounts, exemptions, verification levels,
users, roles, approvers, rule versions or delivery state can be supplied here.
Unknown columns are rejected rather than ignored. A label does not prove source
authenticity or that submitted content is actually synthetic.

## Pure function and explicit conflict context

```python
validate_institution_csv(content: bytes, *, existing_identities: tuple[ExistingIdentity, ...])
```

`ExistingIdentity(aicte_id, institution_code)` is a frozen value object. A null
AICTE ID can represent a known legacy identity without a profile. The keyword
argument is mandatory: pass `()` only for an explicitly empty synthetic snapshot.
Missing/None/lazy ORM/malformed context raises `CsvInputError`; the function
never queries for identities. Context strings are compared after trim/uppercase.
It accepts no filename, path, actor, callback or database handle.

Duplicate AICTE IDs **or** institution codes flag every affected CSV row, including
the first. Identity collisions are detected even if another field in that row is
invalid. Any match against supplied existing identities is a conflict, including
an otherwise identical replay: no update/upsert is inferred. Legacy codes still
block a duplicate code even without an AICTE ID. Responses do not disclose the
existing institution's name or a database primary key.

## Output contract and errors

The returned plain dictionary is a detached in-memory validation result:

- `format`, `simulation_label`, `source_sha256`: version, SIMULATED, exact byte hash.
- `status`: VALID or INVALID; means syntactic/context validation only.
- `row_count`, `valid_count`, `invalid_count`.
- `valid_rows`: `{row, values}` entries; normalized strings only, no model objects.
- `errors`: `{row, field, code}` entries, with no raw rejected values.

`row` is a logical CSV record number: header=1, first data record=2. Quoted
multiline records count once even though their field newlines are rejected.
Row errors are deterministic in row/lexicographic-field-name/code order; header
errors follow the canonical column order, then unknown/duplicate-header codes.
One field's first failure is
reported in this order: control character, blank, formula prefix, length, semantic
syntax/enum. Duplicate/existing conflicts may additionally be reported.

| Error codes | Meaning |
|---|---|
| EMPTY_FILE, FILE_TOO_LARGE, INVALID_UTF8, CSV_SYNTAX, ROW_LIMIT, NO_DATA | File unusable or exceeds demo bounds |
| HEADER_MISSING, HEADER_UNKNOWN, HEADER_DUPLICATE | Missing/unknown/repeated columns |
| EMPTY_ROW, COLUMN_COUNT | Invalid record layout (`field=__row__`) |
| CONTROL_CHARACTER, REQUIRED, FORMULA_PREFIX, TOO_LONG | Invalid field content |
| INVALID_TOKEN, INVALID_EMAIL, INVALID_CHOICE, NOT_SIMULATED | Field-specific error |
| DUPLICATE_IDENTITY, EXISTING_IDENTITY | Collision within file or explicit context |

File/header failures use `row=None`. They discard all candidate rows, return
`row_count=None`, `invalid_count=None`, `valid_count=0` and INVALID: a truncated
parse must not look like a complete preview. Row-only errors retain independently
valid candidates but keep overall INVALID. **No subset is committed by this
function.** A future commit's partial/all-or-nothing policy needs agreement.

## Acceptance tests

1. Valid Unicode, quoted commas, leading zeros, BOM/CRLF and reordered headers
   produce exact expected strings with SIMULATED provenance and no writes.
2. Missing/extra/duplicate headers, invalid encoding/quoting, limits and empty
   files fail explicitly; a late parse error discards earlier candidates.
3. Missing/long/invalid fields, formulas, hidden controls and forged administrative
   columns produce precise row/field codes without echoing rejected values.
4. Both sides of duplicate identities fail after normalization. Existing context
   conflicts fail, including legacy institutions; unrelated candidates remain valid.
5. Repeated calls are deterministic, inputs unchanged, returned values detached.
   Run tests with database access forbidden and a standalone no-settings example.
6. All labelled synthetic cases match independently written expected outcomes;
   original portal, S1/S2, frozen S2 cases and S3 preparation still pass.

## Deferred integration

K1/S2 must supply authorization/scope, validated upload handling, fresh complete
identity context, entity versions and entity-appropriate audit. A future commit
must revalidate against fresh data, handle concurrent uniqueness conflicts
atomically and preserve provenance; source hashes are not authorization or
commit tokens. Real data requires an authorized source and confirmed identity
mapping. No actual AICTE service, HTTP import, preview screen, commit workflow,
notifications, reports or KPI implementation is added now.
