# S7: AI release summary

`POST /api/releases/{id}/ai-summary` accepts `{ "version": <current case version> }` from the assigned clearance unit or an authority user. It first applies the normal case scope and optimistic-version check.

The feature supplies only structured case facts: path, declarations, document kinds/count, clearance statuses, penalties, letter state and a short audit-action history. It sends no PDF, file content, document name, evidence reference, person name or raw decision reason.

The response always describes an advisory result and, when successful, has a short `summary` plus at most five `{field, severity, message}` risk flags. Every rendered result is labelled **AI-generated: verify before use**. The service cannot call a case workflow or modify workflow state.

Successful output is reused by the deterministic SHA-256 of the structured case payload, which includes the case version. Each provider attempt, disabled request and failure has an `AiRun` audit row using operation `RELEASE_SUMMARY`. With `AI_ENABLED=false`, missing configuration, timeout or invalid model JSON, the page remains usable and tells the reviewer to continue manual review.

For a real provider run set `AI_ENABLED=true` and `ANTHROPIC_API_KEY` only for approved synthetic data. The API model remains `claude-opus-5-5`; it is never required for the release journey.
