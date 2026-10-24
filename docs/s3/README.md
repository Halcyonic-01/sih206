# S3 preparation only

- [Screen specification](SCREEN_SPEC.md): institution list/detail and requirement
  calculator, including states, scope, accessibility and planned acceptance cases.
- [Synthetic fixtures](fixtures.json): presentation examples with explicit actor,
  state, input context and expected display. All data is fictional/SIMULATED.
- [Contract review](CONTRACT_REVIEW.md): mapping to actual S1/S2 sources, missing
  response fields, integration dependencies and unresolved team decisions.
- [Offline validator](validate_fixtures.py): repeatable preparation gate, with
  negative tests in `obligations/tests/test_s3_fixtures.py`.

No React setup, components, routes, API adapters, database seed or product feature
was created. The existing S1/S2 implementation is unchanged. S3 implementation
still needs K2's shell and the agreed S2/K1/Y1 integrations.

## Fixture contract

`fixture_format` is a local presentation format, not a proposed replacement for
the API's JSON envelope. Each scenario has a unique `id`, `screen`, `state`,
synthetic `actor`, `screen_data`, `expected_display` and optional S2 lineage.
Reusable entities are explicitly synthetic and referenced by key; consumers must
resolve them only for the selected scenario. These are not a mock HTTP server.
The scenarios are alternative snapshots, not one combined database or timeline.

All money is integer paise and all dates are date-only ISO strings. Values are
small enough for the proposed JS-safe range. Calculation input snapshots are
included only for ready assessment/preview cases. They can be checked against
the existing S2 functions in memory, without inserting fixtures into the database.
No original S2 labels or evaluation records were changed.

The ten-year presentation cases scale the existing arithmetic scenarios to
100 lakh and supply explicit synthetic dates. They are not additional approved
policy labels. S2 lineage IDs identify conceptual examples, not byte-identical
copies of the frozen 76-case regression dataset.

## Usage boundaries

Use these examples only when actual isolated components are authorized within
K2's project. They must not become production bundled tenant data, automatic
fallbacks after an API failure or substitutes for authenticated server scope.
No fixture contains credentials, a real AICTE identity, a real contact, document
bytes or a live bank verification. Contact examples use `example.invalid`.

The supplied action text is a simulated presentation example. It neither assigns
a task nor sends a notification. Do not infer permissions or financial decisions
from a fixture's actor, screen state, status text or a zero shortfall.

## Read the examples

Start with `detail-covered`, then compare `detail-shortfall`, `detail-term-gap`,
`detail-unknown` and `detail-adapter-unavailable`. Next inspect `calculator-preview`
and its invalid/conflict/unavailable states. List and access-denied scenarios
specify expected presentation without pretending the corresponding HTTP requests
have been tested. `http_status_hint` is illustrative and is not a server response.

## Repeatable validation

From the repository root after the normal Python dependency setup:

```powershell
.\.venv\Scripts\python.exe docs/s3/validate_fixtures.py
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_s3_fixtures
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test portal.tests
.\.venv\Scripts\python.exe manage.py test
```

The validator accepts an optional `--fixtures path/to/candidate.json`. Valid v1
data prints `result: passed`, 19 scenarios, seven calculation cases, one expected
rejection and zero database queries, then exits 0. Invalid JSON or a failed
invariant exits 1. It reads local files only; it neither seeds the database nor
changes the fixtures. Django must be installed but a migrated database is not
required for this validator. Every configured Django connection has a query
rejection wrapper; its unit tests additionally use `SimpleTestCase`.

The ten validator tests include deliberately corrupted in-memory copies: missing
or duplicate scenarios, bad lineage, wrong money/multiplier, cross-scope records,
protected data in denied states, nulls changed to zero, missing findings, wrong
proof deadlines/fingerprints, a supposedly invalid input that actually succeeds,
stale previews and malformed CLI JSON. Source labels remain unchanged.

Windows regression upload tests need normal OS temporary-directory access.
If sandbox restrictions produce `PermissionError`, rerun with the required
filesystem access; never disable upload checks or count the restricted run as
a pass. Test data is isolated by the existing suite.

## Validation record

- JSON and 19 unique scenarios checked: five list, eight detail and six calculator
  states. All references to the existing S2 labelled scenario IDs resolve.
- Seven calculation-bearing cases checked against S2 without database queries:
  five coverage/finding examples, one successful calculator example and one
  deliberately unsupported input returning the expected controlled error.
- Display amounts checked in paise: 100 lakh required, 60 lakh held and 40 lakh
  shortfall in the shortfall example. The term-gap example remains short of full
  duration even with sufficient amount today.
- List/detail actor scope and empty protected data in the two access-error states
  checked as fixture invariants. This does not test real API authorization.
- Local documentation links and source S1/S2 preservation checked. The private
  verification summary is under ignored `data/s3-preparation-verification.json`.

No browser, React build, accessibility execution, HTTP request or end-to-end S3
UI pass is claimed. See [verification results](VERIFICATION.md) for this local
preparation checkpoint. Application and existing S1/S2 test files did not change.
