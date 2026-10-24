# P2 — institution and obligation APIs on the shared platform

Implemented locally on 25 October 2026, based on merged commit `e789c30` with
uncommitted P1 changes preserved. Branch: `s/P2-platform-institution-api`.
No push, shared/teammate file changes, new migration or P3 implementation.

## Scope and route registration

`obligations/api_urls.py` is the S2 extension automatically loaded by K1. No
config/urls.py or portal/api/urls.py edit is needed. Existing no-trailing-slash
owned paths are preserved:

| Method | Path under /api/ | Behavior |
|---|---|---|
| GET / POST | institutions | Scoped, paginated list / officer-only audited create |
| GET / PATCH | institutions/{id} | Scoped detail / versioned officer master update |
| GET / POST | institutions/{id}/programme-approvals | Scoped page / officer create |
| GET / PATCH | programme-approvals/{id} | Scoped detail / versioned officer update |
| GET / POST | institutions/{id}/obligations | Scoped page / officer create |
| GET / PATCH | obligations/{id} | Scoped detail/assessment / versioned officer update |
| POST | calculator | Scoped read-only preview; session/CSRF still required |
| GET | rules | Paginated draft metadata, no rule publication |

The legacy harness remains for earlier report/release tests. P2 does not register
reports, imports, KPIs, releases or public verification in the default app. Those
routes remain future S4/S5 integration work. No frontend routes are mounted.

## Shared conventions now used

- Authentication/permissions inherit K1's configured session authentication and
  IsAuthenticated behavior. Signed-out requests return 401; CSRF protects writes.
- Owned domain errors normalize to platform-recognized exceptions before K1's
  existing exception handler. The envelope is `{detail, code, errors?}`. Invalid
  input is 400, permission denied 403, missing/foreign 404, stale/identity conflict
  409 and dependency/database/storage unavailable 503. Internal database or
  dependency exception text is not returned.
- Because the owned base is shared by the earlier S4/S5 harness views, those
  views also inherit K1 auth/errors now. Existing owned/release regression tests
  pass; this does not register their routes or complete their integration.
- Master/child/rule lists use StandardPagination: count, page, page_size,
  total_pages, results; default 25 and page_size capped at 100. Invalid/out-of-range
  pages follow platform 404 semantics. This replaces the old owned list wrapper.
- Responses retain no-store and K1 request IDs.
- Officer/authority institution-list searches call K4 log_access before responding.
  Logs contain entity/action/request ID and generic search detail, not raw search
  terms. Logging failure prevents disclosure and returns safe 503.
- OpenAPI request/read/page/error serializers describe actual snapshot keys and
  source evidence. An owned serializer extension keeps version/reason required
  on PATCH even though business data fields are partial. Allowed choice codes are
  documented in field descriptions; services enforce the actual values.

## Explicit conservative master access

| Role | Read institution/programme/obligation/rule data | Write masters |
|---|---|---|
| Institution | Own institution only | Denied |
| Officer | All institution master records | Allowed with reason/version |
| Authority | All institution master records | Denied |
| Clearance | Denied | Denied |
| Auditor | Denied | Denied |
| Inactive, unassigned or ambiguous role | Denied | Denied |

This preserves the existing master service policy. K4's instrument/history access
does not automatically authorize access to unsubmitted institution master data.
There is no geographic master-scope helper in the merged platform; P2 invents no
regional restriction. Any future auditor/clearance master access needs an explicit
policy change and tests. Authorization is enforced server-side regardless of UI.

## Data, audit and remaining boundaries

- Existing atomic service writes, optimistic versions, reasons, constraints and
  MasterAudit remain. Create has no existing entity version; PATCH requires a
  positive integer version. Identity conflicts are generic and transactional.
- Money writes require exact positive safe integer paise. Legacy read values
  beyond 2^53−1 retain the existing exact decimal-string encoding; OpenAPI records
  both possible read representations. No financial calculation was changed.
- Missing holding integration remains unavailable with null coverage/findings/
  holdings/open_actions. No empty linked ledger, zero shortfall, receipt date,
  exemption, current policy or bank verification is inferred.
- Calculator results retain draft rule/source/version/fingerprint evidence and
  do not write obligations or audit mutations.
- Y1 linkage, Y2/Y3 receipts, P4 policy/rule-source integration, P5 reports and P6/P7
  entity-audit/hash-chain integration remain pending. No fake instrument is used
  to force master audits into an instrument-specific audit stream.

## Verification and reproduction

From the repository root with both existing Python locks installed:

```powershell
.\.venv\Scripts\python.exe manage.py test obligations.tests.test_platform_api obligations.tests.test_owned_api obligations.tests.test_casework --noinput
.\.venv\Scripts\python.exe manage.py spectacular --validate --fail-on-warn --file data/p2-schema.yml
.\.venv\Scripts\python.exe -m evaluation.s2.run --output data/p2-s2-evaluation.json
```

New default-route acceptance tests cover registration, 401/CSRF, role matrix,
foreign/missing equivalence, scoped pagination/cap, allowed/denied/invalid/stale
master and child writes, audit rollback, duplicate identities, calculator evidence,
unknown sources, exact large legacy money, access-log failure, parser/dependency
errors and required PATCH fields in the shared schema. Tests run through
config.urls and real session middleware; no replacement shared auth setup exists.

An initial new-test arithmetic expectation was corrected from an incorrect amount
to the literal draft rule's 15 lakh INR × 2 = 300,000,000 paise. Existing source
labels were unchanged. Initial OpenAPI enum/operation-ID warnings were resolved
inside owned schema declarations; shared settings were not altered. PATCH schema
generation initially omitted mandatory version/reason; the owned serializer
extension fixes that and tests now resolve the actual generated component refs.

### Final results

| Check | Actual result |
|---|---|
| Pre-change owned API/casework baseline | 31 passed, 4.395 seconds |
| New platform acceptance + existing owned API/casework | **47 passed**, 7.003 seconds (16 new tests) |
| Original portal suite | **159 passed**, 33.853 seconds |
| Full backend suite | **546 run: 545 passed, 1 failed**, 128.154 seconds |
| Django system check / migration drift | Passed / no changes detected |
| OpenAPI validate with --fail-on-warn | Passed, no warnings/errors |
| S2 synthetic evaluation | **76/76 passed**; original labels unchanged |
| Preserved P1 shared Vitest tests | **42 passed**, 2.87 seconds |
| Frontend typecheck + production build | Passed; Vite build 873ms |
| Protected shared/teammate tracked-source comparison | Unchanged |
| git diff --check | Passed |

The full-backend failure remains the pre-existing Windows POSIX-mode assertion
in access.tests.test_accesslog.SeedStaffTests.test_creates_accounts_units_and_private_credentials_once
(`54 != 0`). No teammate test or source was changed. The complete shared frontend
suite was not rerun for this backend-only P2 change; its existing audit timeout
failures remain unresolved. Focused P1 tests and the shared build were rerun.

Counts overlap. All API acceptance tests use isolated databases; none are a claim
of a browser journey or real banking/regulatory accuracy. No live institution,
obligation, account or financial demo record was created in this pass.

Private logs and generated schema/evaluation outputs are under ignored data/p2-*.
P1 changes and the pre-existing local audit/implementation-plan files are preserved.
All new P2 work is local and uncommitted; P3 has not started.
