# Owned S3/S4/S6 components — no separate React app

These are standalone React/TypeScript feature components intended for K2's shared
frontend. No package.json, Vite setup, router, auth provider, shared HTTP client,
theme or AppShell is created. Native semantic controls can be mounted/styled in
the shared Ant Design shell; its visual integration has not been tested here.

## Exports

`index.ts` exports InstitutionList, InstitutionDetail, ObligationCard, Calculator,
Reports, InstitutionImport, Kpis, ReleaseWizard, ReleaseCase, ClearanceQueue and
PublicVerification. Navigation is injected (`onSelect`, `onCreated`), so there are
no invented router imports or menu registrations. Components never load fixtures.

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

## Repeatable isolated checks

From repository root, with Node available, install test tooling into ignored data:

```powershell
npm.cmd install --prefix data/saksham-ui-tools --no-audit --no-fund react@19.3.0 react-dom@19.3.0 typescript@7.0.2 @types/react@19.3.0 @types/react-dom@19.3.0 react-test-renderer@19.3.0
.\.venv\Scripts\python.exe frontend/src/features/saksham/verify.py
```

On macOS/Linux use `npm` and `.venv/bin/python`. The Python checker creates only an
ignored TypeScript config/build under data, invokes the compiler and runs 11 Node
component tests. Missing tools fail explicitly. Nothing changes the shared frontend
setup. react-test-renderer currently emits a deprecation notice; these are isolated
component tests, not browser/layout/accessibility tests. Migrate them to K2/K3's
agreed runner during integration rather than installing a second app test stack.

Checks cover exact money/nulls, minimal public data, approval versus completion,
server action gating, failed services, old-identity response races, missing
questionnaire, ignored mutation projections, public revocation/errors and an
unspecified KPI cohort. The backend suites separately exercise real owned API views.

Still required in the merged app: route/client/auth integration, proper browser
tests, 360px/desktop visual review, keyboard/screen-reader checks, target-browser
PDF opening/downloads, fully connected source adapters and offline rehearsal.
