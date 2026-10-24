# Owned S3/S4/S6 components — no separate React app

**P3 update, 25 October 2026:** institution list/detail/calculator routes are now
mounted through K2's feature registry, with shared auth and an owned adapter to
its real HTTP client. See [P3 implementation and verification](../../../../docs/owned/P3_IMPLEMENTATION.md).
Release/report/KPI/import components remain unmounted. The transport/document
capability descriptions below still apply to their later integration.

These React/TypeScript feature components now compile and test within K2's merged
frontend. No package, Vite setup, replacement router/auth provider/shared HTTP
client/theme/AppShell is created. Institution pages now use a shared Card and scoped
responsive CSS; other components still need their later integration and visual review.

## Exports

`index.ts` exports InstitutionList, InstitutionDetail, ObligationCard, Calculator,
Reports, InstitutionImport, Kpis, ReleaseWizard, ReleaseCase, ClearanceQueue and
PublicVerification. Navigation is injected (`onSelect`, `onCreated`), so there are
no competing router is created. P3's route/page wrappers connect the institution
components to real navigation and data. Components never load fixtures.

K2 supplies one stable `Transport` object:

```typescript
interface Transport {
  get<T>(path: string, signal?: AbortSignal): Promise<T>;
  post<T>(path: string, body: unknown | FormData): Promise<T>;
  download(path: string): Promise<void>;
}
```

Adapt this interface to `api/client.ts`, not the reverse. The implementation must
use same-origin sessions/CSRF, reject unsafe cross-origin downloads, honor abort
signals, and reject errors with a numeric `status`. It must not set a JSON content
type on FormData, replay writes automatically or use localStorage auth tokens.
Download accepts the server-provided protected relative document path or owned
letter/report path; it must retain cookies and safely release any blob URL it uses.

Every authenticated component gets `identityKey`: an opaque session/role/scope
generation that changes on login, logout and permission changes, even if the same
user signs back in. It is not a credential. The remote hook discards late responses
and previous identity data. K2 still handles global session expiry and navigation.

## Release wizard inputs

Pass scoped `instrumentId`, `obligationId`, `instrumentVersion` and server-supplied
`canRequest`. `questionnaire` must contain the real reviewed template reference in
`version` and its canonical `{id,label}` questions. Missing template blocks the
wizard; no sample questions ship with the components. Answers are explicit yes/no,
not default false. Submission carries the captured `template_ref`.

Supply `documents` as Y4/Y3's authorized typed upload/viewer component, plus
`documentsReady` and `documentPath` identifying the path for which that document
checklist was assessed. On `onPathChange(path)`, fetch the new checklist and invalidate
old readiness. Path mismatch disables progression. No guessed document endpoint,
fake PDF or client assertion can replace backend source validation.

The parent should load capability/template/source metadata before enabling the
wizard, and refresh on instrument changes. These metadata contracts are pending;
their absence is intentionally visible and blocked. The wizard is not usable end
to end simply because isolated components compile.

Case screens render server saved status/monitoring separately from advisory
readiness; they ignore mutation projections and reload saved state. Controls
follow scoped `actions`/`can_decide`, require a reason and disable while pending.
After 409/503, saved state reloads without replaying the mutation. PublicVerification
only accepts five public record fields and has no private case/document links.

## Repeatable checks in the shared frontend

Use Node 22.12 or newer and the committed frontend lock. From frontend/:

```powershell
npm.cmd ci --no-audit --no-fund
npm.cmd run typecheck
npm.cmd test -- src/features/saksham/
npm.cmd test
npm.cmd run build
```

On macOS/Linux use npm. From the repository root the existing compatibility entry
point also works: `.\.venv\Scripts\python.exe frontend/src/features/saksham/verify.py`
(or `.venv/bin/python` on macOS/Linux). It runs the shared type-check and owned
Vitest tests, stopping on a failing command. It no longer generates a separate
TypeScript configuration or imports tools from data/saksham-ui-tools.

client.test.ts covers exact paise/nulls, decimal parsing and boundaries, and the
minimal public record allowlist. components.test.tsx renders the actual components
with Testing Library, shared jsdom setup and explicitly fake injected sources.
All 11 original test behaviors have been migrated, with additional money boundary
cases. P3 adds transport and mounted-route coverage (63 owned cases in total).
The obsolete tests.cjs runner
is removed after equivalent migrated tests pass; react-test-renderer is not used.
No dependency, shared setup, timeout or compiler option was changed.

The original behaviors preserved are: integer money/nulls; public allowlist;
approval versus completion; READY not granting actions; failed service without
fallback; old identity response discarded; missing questionnaire blocking;
mutation projection ignored in favor of saved state; revoked public record without
private links; public 404 versus 503; and no KPI request without a selected cohort.
The backend suites separately exercise real owned API views. These DOM unit tests
do not verify routing, real auth/HTTP, browser layout, PDF viewing or accessibility.

Still required in the merged app: route/client/auth integration, proper browser
tests, 360px/desktop visual review, keyboard/screen-reader checks, target-browser
PDF opening/downloads, fully connected source adapters and offline rehearsal.
