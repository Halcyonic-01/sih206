import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, onUnauthorized } from '@/api/client';
import { platformTransport } from './platformTransport';

const fetchMock = vi.fn<typeof fetch>();
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data),
  { status, headers: { 'Content-Type': 'application/json' } });
beforeEach(() => { vi.stubGlobal('fetch', fetchMock); document.cookie = 'csrftoken=p3-test; path=/'; });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); fetchMock.mockReset(); });

describe('owned transport consuming the real shared client', () => {
  it('delegates GET abort and same-origin session behavior', async () => {
    fetchMock.mockResolvedValue(json({ count: 0, results: [] }));
    const signal = new AbortController().signal;
    await platformTransport.get('/api/institutions', signal);
    expect(fetchMock).toHaveBeenCalledWith('/api/institutions', expect.objectContaining({ signal, credentials: 'same-origin' }));
  });

  it('delegates JSON CSRF and multipart without inventing a content type', async () => {
    fetchMock.mockImplementation(async () => json({}));
    await platformTransport.post('/api/calculator', { approvals: [] });
    expect(fetchMock).toHaveBeenLastCalledWith('/api/calculator', expect.objectContaining({
      headers: expect.objectContaining({ 'X-CSRFToken': 'p3-test', 'Content-Type': 'application/json' }),
      body: JSON.stringify({ approvals: [] }), method: 'POST',
    }));
    const form = new FormData();
    form.set('file', new File(['synthetic'], 'synthetic.txt'));
    await platformTransport.post('/api/example', form);
    const request = fetchMock.mock.calls.at(-1)?.[1];
    expect(request?.body).toBe(form);
    expect(request?.headers).not.toHaveProperty('Content-Type');
  });

  it.each(['https://example.invalid/api/private', '//example.invalid/api/private',
    '/api/../../private', '/api/\\example.invalid/private', '/api/private#fragment', '/legacy/private'])
    ('rejects unsafe or unsupported path %s before HTTP', path => {
      expect(() => platformTransport.get(path)).toThrow('Unsafe API path');
      expect(() => platformTransport.post(path, {})).toThrow('Unsafe API path');
      expect(() => platformTransport.download(path)).toThrow('Unsafe API path');
      expect(fetchMock).not.toHaveBeenCalled();
    });

  it('preserves shared errors and does not replay a conflict', async () => {
    fetchMock.mockResolvedValue(json({ detail: 'Reload', code: 'conflict' }, 409));
    await expect(platformTransport.post('/api/calculator', {})).rejects.toMatchObject({ status: 409, code: 'conflict' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('lets the shared client invalidate auth on 401', async () => {
    const listener = vi.fn();
    const stop = onUnauthorized(listener);
    try {
      fetchMock.mockResolvedValue(json({ detail: 'Sign in', code: 'not_authenticated' }, 401));
      await expect(platformTransport.get('/api/institutions')).rejects.toBeInstanceOf(ApiError);
      expect(listener).toHaveBeenCalledOnce();
    } finally { stop(); }
  });
});
