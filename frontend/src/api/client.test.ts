import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, buildUrl, onUnauthorized, readCookie, setStepUpHandler } from './client'

function reply(status: number, body?: unknown, headers: Record<string, string> = {}) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json', ...headers },
  })
}

describe('api client', () => {
  const fetchMock = vi.fn<typeof fetch>()
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    document.cookie = 'csrftoken=tok123; path=/'
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
  })

  it('builds /api URLs and drops empty query values', () => {
    expect(buildUrl('/records/', { q: 'abc', page: 2, empty: '', none: undefined })).toBe('/api/records/?q=abc&page=2')
    expect(buildUrl('/audit/', { action: ['A', 'B'], q: 'x' })).toBe('/api/audit/?action=A&action=B&q=x')
    expect(buildUrl('/audit/', { action: [] })).toBe('/api/audit/')
    expect(buildUrl('records/')).toBe('/api/records/')
    expect(buildUrl('/api/health/')).toBe('/api/health/')
  })

  it('sends the CSRF header on writes but not on reads', async () => {
    fetchMock.mockImplementation(async () => reply(200, { ok: true }))
    await api('/things/')
    await api('/things/', { method: 'POST', json: { a: 1 } })
    const [, read] = fetchMock.mock.calls[0]!
    const [, write] = fetchMock.mock.calls[1]!
    expect((read!.headers as Record<string, string>)['X-CSRFToken']).toBeUndefined()
    expect((write!.headers as Record<string, string>)['X-CSRFToken']).toBe('tok123')
    expect((write!.headers as Record<string, string>)['Content-Type']).toBe('application/json')
    expect(write!.credentials).toBe('same-origin')
  })

  it('fetches a CSRF cookie first when none exists', async () => {
    document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
    fetchMock.mockImplementation(async (url) => {
      if (String(url) === '/api/auth/csrf/') {
        document.cookie = 'csrftoken=fresh; path=/'
        return reply(200, { csrfToken: 'fresh' })
      }
      return reply(200, {})
    })
    await api('/things/', { method: 'POST', json: {} })
    expect(String(fetchMock.mock.calls[0]![0])).toBe('/api/auth/csrf/')
    expect((fetchMock.mock.calls[1]![1]!.headers as Record<string, string>)['X-CSRFToken']).toBe('fresh')
  })

  it('does not set Content-Type for multipart bodies', async () => {
    fetchMock.mockImplementation(async () => reply(201, {}))
    const form = new FormData()
    form.append('file', new Blob(['x']), 'a.pdf')
    await api('/documents/', { form })
    const headers = fetchMock.mock.calls[0]![1]!.headers as Record<string, string>
    expect(headers['Content-Type']).toBeUndefined()
    expect(headers['X-CSRFToken']).toBe('tok123')
  })

  it('maps the error envelope for 400, 403, 404 and 409', async () => {
    fetchMock.mockResolvedValueOnce(reply(400, { detail: 'Invalid input.', code: 'validation_error', errors: { amount: ['Required.'] } }))
    await expect(api('/x/')).rejects.toMatchObject({ status: 400, isValidation: true, errors: { amount: ['Required.'] } })
    fetchMock.mockResolvedValueOnce(reply(403, { detail: 'No.', code: 'permission_denied' }))
    await expect(api('/x/')).rejects.toMatchObject({ status: 403, isForbidden: true, message: 'No.' })
    fetchMock.mockResolvedValueOnce(reply(404, { detail: 'Not found.', code: 'not_found' }))
    await expect(api('/x/')).rejects.toMatchObject({ isNotFound: true })
    fetchMock.mockResolvedValueOnce(reply(409, { detail: 'This record changed.', code: 'conflict' }))
    const error = await api('/x/', { method: 'PATCH', json: {} }).catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).isConflict).toBe(true)
  })

  it('notifies listeners on 401 except for auth endpoints', async () => {
    const listener = vi.fn()
    const off = onUnauthorized(listener)
    fetchMock.mockImplementation(async () => reply(401, { detail: 'Auth.', code: 'not_authenticated' }))
    await expect(api('/records/')).rejects.toMatchObject({ isUnauthorized: true })
    expect(listener).toHaveBeenCalledTimes(1)
    await expect(api('/auth/me/')).rejects.toBeInstanceOf(ApiError)
    expect(listener).toHaveBeenCalledTimes(1)
    off()
  })

  it('survives non-JSON failures and network errors', async () => {
    fetchMock.mockResolvedValueOnce(new Response('<html>Bad gateway</html>', { status: 502 }))
    await expect(api('/x/')).rejects.toMatchObject({ status: 502, code: 'error' })
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(api('/x/')).rejects.toMatchObject({ status: 0, code: 'network_error' })
  })

  it('returns undefined for 204', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }))
    expect(await api('/auth/logout/', { method: 'POST', json: {} })).toBeUndefined()
  })

  it('reads cookies safely', () => {
    document.cookie = 'a=1; path=/'
    expect(readCookie('a')).toBe('1')
    expect(readCookie('missing')).toBeNull()
  })

  it('asks for a fresh authenticator code on mfa_step_up_required, then repeats the request once', async () => {
    fetchMock
      .mockResolvedValueOnce(reply(403, { detail: 'Enter a code.', code: 'mfa_step_up_required' }))
      .mockResolvedValueOnce(reply(200, { done: true }))
    const handler = vi.fn(async () => undefined)
    const remove = setStepUpHandler(handler)
    await expect(api('/releases/1/approve', { method: 'POST', json: { version: 3 } })).resolves.toEqual({ done: true })
    expect(handler).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[1]![1]!.body).toBe(JSON.stringify({ version: 3 }))
    remove()
  })

  it('throws the original error when the step-up is cancelled, and never loops', async () => {
    fetchMock.mockImplementation(async () => reply(403, { detail: 'Enter a code.', code: 'mfa_step_up_required' }))
    const remove = setStepUpHandler(async () => { throw new Error('cancelled') })
    await expect(api('/releases/1/issue', { method: 'POST', json: {} })).rejects.toMatchObject({ code: 'mfa_step_up_required' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    remove()
    fetchMock.mockClear()
    const again = setStepUpHandler(async () => undefined)
    await expect(api('/releases/1/issue', { method: 'POST', json: {} })).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).toHaveBeenCalledTimes(2) // one retry after a confirmed code, not more
    again()
  })
})
