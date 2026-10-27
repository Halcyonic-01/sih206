/**
 * The only HTTP entry point for the app (same-origin session cookie + X-CSRFToken).
 * No tokens are kept in localStorage. Errors always arrive as ApiError built from the server envelope
 * {detail, code, errors?}:
 *   400 -> field errors in `errors`        401 -> session ended (listeners are notified)
 *   403 -> not allowed                      404 -> missing or out of scope
 *   409 -> record changed, reload           429 -> throttled / locked out
 */

export type Role = 'institution' | 'officer' | 'authority' | 'clearance' | 'auditor'

export interface Page<T> {
  count: number
  page: number
  page_size: number
  total_pages: number
  results: T[]
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly errors: Record<string, string[]>

  constructor(status: number, code: string, detail: string, errors: Record<string, string[]> = {}) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.errors = errors
  }

  get isConflict() { return this.status === 409 }
  get isForbidden() { return this.status === 403 }
  get isNotFound() { return this.status === 404 }
  get isUnauthorized() { return this.status === 401 }
  get isValidation() { return this.status === 400 }
}

export type QueryValue = string | number | boolean | null | undefined | (string | number)[]
export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** JSON body. */
  json?: unknown
  /** Multipart body (file uploads). The browser sets the boundary, so never set Content-Type. */
  form?: FormData
  query?: Record<string, QueryValue>
  signal?: AbortSignal
}

const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])
const unauthorizedListeners = new Set<() => void>()
/** One Idempotency-Key per user intent. Sending the same write again within INTENT_SECONDS (a double click, a retry after a
 * network error or a 5xx) reuses the key, so the server answers with the first result instead of creating a duplicate.
 * The key is forgotten once the server has given a final answer (success or a 4xx), so the next attempt is a new one. */
const INTENT_SECONDS = 120
const intents = new Map<string, { key: string; at: number }>()

function intentFingerprint(method: string, path: string, options: RequestOptions) {
  let body = ''
  if (options.form) {
    body = Array.from(options.form.entries()).map(([name, value]) =>
      `${name}=${typeof value === 'string' ? value : `${value.name}:${value.size}:${value.lastModified}`}`).join('&')
  } else if (options.json !== undefined) {
    body = JSON.stringify(options.json)
  }
  return `${method} ${buildUrl(path, options.query)} ${body}`
}

function intentKey(fingerprint: string) {
  const now = Date.now()
  for (const [key, value] of intents) if (now - value.at > INTENT_SECONDS * 1000) intents.delete(key)
  const known = intents.get(fingerprint)
  if (known) return known.key
  const created = { key: globalThis.crypto?.randomUUID?.() ?? `${now.toString(36)}-${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`, at: now }
  intents.set(fingerprint, created)
  return created.key
}

let stepUpHandler: (() => Promise<void>) | null = null

/** The step-up dialog registers here. When an action answers 403 `mfa_step_up_required`, the handler asks for an
 * authenticator code; once it resolves the request is sent once more. If it rejects (cancelled) the original error is thrown. */
export function setStepUpHandler(handler: (() => Promise<void>) | null) {
  stepUpHandler = handler
  return () => { if (stepUpHandler === handler) stepUpHandler = null }
}

/** AuthProvider subscribes here so any 401 returns the user to the login page. */
export function onUnauthorized(listener: () => void) {
  unauthorizedListeners.add(listener)
  return () => { unauthorizedListeners.delete(listener) }
}

export function readCookie(name: string): string | null {
  for (const part of document.cookie.split(';')) {
    const [key, ...rest] = part.trim().split('=')
    if (key === name) return decodeURIComponent(rest.join('='))
  }
  return null
}

let csrfRequest: Promise<void> | null = null
async function ensureCsrfCookie() {
  if (readCookie('csrftoken')) return
  csrfRequest ??= fetch('/api/auth/csrf/', { credentials: 'same-origin' })
    .then(() => undefined)
    .finally(() => { csrfRequest = null })
  await csrfRequest
}

export function buildUrl(path: string, query?: Record<string, QueryValue>) {
  const url = path.startsWith('/api/') ? path : `/api${path.startsWith('/') ? '' : '/'}${path}`
  if (!query) return url
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (Array.isArray(value)) {
      value.forEach((item) => params.append(key, String(item))) // repeated key: ?action=A&action=B
    } else if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value))
    }
  }
  const text = params.toString()
  return text ? `${url}${url.includes('?') ? '&' : '?'}${text}` : url
}

async function toApiError(response: Response): Promise<ApiError> {
  let body: { detail?: string; code?: string; errors?: Record<string, string[]> } = {}
  try {
    body = await response.json()
  } catch {
    // Non-JSON error (proxy page, 502): fall through to a generic message.
  }
  const fallback: Record<number, string> = {
    401: 'Your session has ended. Sign in again.',
    403: 'You do not have permission to do this.',
    404: 'This item was not found.',
    409: 'This record changed. Reload it before trying again.',
    503: 'The service is temporarily unavailable. Try again shortly.',
  }
  return new ApiError(
    response.status,
    body.code ?? 'error',
    body.detail ?? fallback[response.status] ?? `Request failed (${response.status}).`,
    body.errors ?? {},
  )
}

async function send(path: string, options: RequestOptions, retriedAfterStepUp = false): Promise<Response> {
  const method = options.method ?? (options.json !== undefined || options.form ? 'POST' : 'GET')
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (!SAFE_METHODS.has(method)) {
    await ensureCsrfCookie()
    const token = readCookie('csrftoken')
    if (token) headers['X-CSRFToken'] = token
    if (!path.includes('/auth/')) headers['Idempotency-Key'] = intentKey(intentFingerprint(method, path, options))
  }
  let body: BodyInit | undefined
  if (options.form) {
    body = options.form
  } else if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.json)
  }
  let response: Response
  try {
    response = await fetch(buildUrl(path, options.query), {
      method, headers, body, credentials: 'same-origin', signal: options.signal,
    })
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error
    throw new ApiError(0, 'network_error', 'Cannot reach the server. Check your connection and try again.')
  }
  if (!SAFE_METHODS.has(method) && (response.ok || (response.status >= 400 && response.status < 500))) {
    intents.delete(intentFingerprint(method, path, options))  // a final answer: the next attempt is a new intent
  }
  if (!response.ok) {
    const error = await toApiError(response)
    if (error.isUnauthorized && !path.includes('/auth/')) unauthorizedListeners.forEach((fn) => fn())
    if (error.code === 'mfa_step_up_required' && stepUpHandler && !retriedAfterStepUp) {
      let confirmed = true
      try { await stepUpHandler() } catch { confirmed = false }
      if (confirmed) return send(path, options, true)
    }
    throw error
  }
  return response
}

export async function api<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(path, options)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** Protected document bytes for the inline PDF viewer, using the shared session/error path. */
export async function documentBlob(path: string): Promise<Blob> {
  return (await send(path, {})).blob()
}

export const get = <T>(path: string, query?: Record<string, QueryValue>, signal?: AbortSignal) =>
  api<T>(path, { query, signal })
export const post = <T>(path: string, json?: unknown) => api<T>(path, { method: 'POST', json: json ?? {} })
export const patch = <T>(path: string, json: unknown) => api<T>(path, { method: 'PATCH', json })
export const upload = <T>(path: string, form: FormData, method: 'POST' | 'PUT' | 'PATCH' = 'POST') =>
  api<T>(path, { method, form })

/** Authenticated file download (reports, exports, documents) through the same error handling. */
export async function download(path: string, query?: Record<string, QueryValue>, fallbackName = 'download') {
  const response = await send(path, { query })
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition)
  const blob = await response.blob()
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = match?.[1] ? decodeURIComponent(match[1]) : fallbackName
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(link.href)
}
