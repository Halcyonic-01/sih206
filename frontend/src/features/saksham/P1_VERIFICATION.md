# P1 frontend compilation and shared component tests

Verified locally on 25 October 2026 against merged baseline `e789c30`.
Local branch: `s/P1-frontend-compilation-tests`. No push or P2 implementation.

## Changes

- client.ts explicitly narrows the parsed whole-number string before BigInt.
  Exact paise arithmetic and existing input/range validation remain intact;
  shared strict compiler settings are unchanged.
- client.test.ts adds shared Vitest tests for money/nulls, exact decimal parsing,
  smallest positive and largest safe amounts, malformed/nonpositive/overflow
  inputs, and the public response allowlist.
- components.test.tsx ports the existing DOM behaviors to Testing Library and
  Vitest, using the actual components and explicitly fake injected test sources.
- verify.py retains the root Python command as a compatibility wrapper around
  shared typechecking and focused Vitest execution. No second toolchain or
  generated TypeScript configuration is required.
- The obsolete tests.cjs/react-test-renderer runner was removed only after all
  equivalent migrated behaviors passed. No tests were disabled or skipped.
- README.md now documents the shared commands and remaining integration limits.

## Original behavior coverage retained

| Original behavior | Shared test location |
|---|---|
| Exact money, null values and INR parsing | client.test.ts, with additional boundary cases |
| Strict separate public record allowlist | client.test.ts |
| Approval keeps monitoring active, completion pending | components.test.tsx |
| READY alone does not grant an authority action | components.test.tsx |
| Service failure cannot fall back to synthetic data | components.test.tsx |
| Old identity response cannot populate a new screen | components.test.tsx; also asserts abort |
| Missing canonical questionnaire blocks the wizard | components.test.tsx |
| Mutation projection ignored; saved state reloaded | components.test.tsx; also checks versions/reason payload |
| Revoked public record has no private links | components.test.tsx |
| Public not-found differs from service failure | components.test.tsx, separate 404/503 cases |
| KPI does not request an unspecified cohort | components.test.tsx |

## Actual verification

| Command | Result |
|---|---|
| Baseline `npm run typecheck` | Reproduced TS2345 at client.ts:28 |
| Final `npm run typecheck` | Passed |
| `npm test -- src/features/saksham/` | **42 passed**, two files, 2.90 seconds |
| Root Python compatibility checker | Passed typecheck and **42 tests**, 3.06 seconds for Vitest |
| `npm run build` | Passed; Vite bundle built in 6.57 seconds |
| Full `npm test` | **67 passed, 2 failed**, 69 total, 35.32 seconds |
| `manage.py check` | Passed |
| `manage.py makemigrations --check --dry-run` | No changes detected |
| `manage.py test portal.tests --noinput` | **159 passed**, 39.620 seconds |
| `manage.py test --noinput` | **529 passed, 1 failed**, 530 total, 126.150 seconds |
| Shared/teammate tracked-source comparison against HEAD | Unchanged |
| `git diff --check` | Passed |

The full frontend failures are existing audit-screen timeouts at
features/audit/audit.test.tsx:54 (event detail) and :64 (filters), both exceeding
the unchanged 5-second timeout. They were among the four baseline timeouts; this
run having two failures does not establish that the other two are fixed.

The backend failure is the existing Windows POSIX-permission assertion in
access.tests.test_accesslog.SeedStaffTests.test_creates_accounts_units_and_private_credentials_once
(`54 != 0`). No teammate implementation, test, timeout or permission setting was
changed to suppress it. The combined regression suite therefore remains red.

Private logs are under ignored data/p1-*.log. Counts overlap and must not be added
as independent scenarios. No browser, PDF, routing, real-auth/API, deployment or
full accessibility verification is claimed. Owned components are still unmounted;
P2 route/API integration has not started. Dependencies, shared test configuration,
auth/client/router/shell, backend services and migrations are unchanged.

P1's owned compile/build/test gates pass; full-project sign-off remains blocked
by the documented teammate-owned baseline failures and later integration work.
