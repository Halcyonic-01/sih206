import { get, post, upload, download } from '@/api/client';
import type { Transport } from './client';

/** Owned adapter only: K2 remains the sole HTTP/session/CSRF implementation. */
function apiPath(path: string): string {
  if (!path.startsWith('/api/') || path.includes('\\')) throw new Error('Unsafe API path');
  const url = new URL(path, window.location.origin);
  if (url.origin !== window.location.origin || !url.pathname.startsWith('/api/') || url.hash) {
    throw new Error('Unsafe API path');
  }
  return path;
}

export const platformTransport: Transport = {
  get<T>(path: string, signal?: AbortSignal) { return get<T>(apiPath(path), undefined, signal); },
  post<T>(path: string, body: unknown | FormData) {
    return body instanceof FormData ? upload<T>(apiPath(path), body) : post<T>(apiPath(path), body);
  },
  download(path: string) { return download(apiPath(path)); },
};
