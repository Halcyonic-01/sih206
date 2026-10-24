import type {Api} from '../features/records/types';

async function checked(response: Response) {
  if (response.ok) return response;
  let detail = '';
  const messages = (value: unknown): string => {
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.map(messages).join(' ');
    if (value && typeof value === 'object') return Object.entries(value).map(([key, text]) =>
      `${['detail', 'errors', 'non_field_errors'].includes(key) ? '' : key.replaceAll('_', ' ') + ': '}${messages(text)}`).join(' ');
    return '';
  };
  try {detail = messages(await response.json());} catch { /* no HTML diagnostics */ }
  const instruction = response.status === 409 ? 'Record changed. Reload before retrying.'
    : response.status === 403 ? 'Access denied or session expired. Sign in again if needed.' : 'Request failed.';
  throw new Error(`${instruction} ${detail}`.trim());
}
export const api: Api = {
  async request<T>(path: string, options?: {method?: string; body?: unknown}): Promise<T> {
    const headers: Record<string, string> = {'Accept': 'application/json'};
    const method = options?.method || 'GET';
    if (method !== 'GET') {
      const token = document.cookie.split('; ').find(v => v.startsWith('csrftoken='))?.slice('csrftoken='.length);
      if (token) headers['X-CSRFToken'] = decodeURIComponent(token);
    }
    let body: BodyInit | undefined;
    if (options?.body instanceof FormData) body = options.body;
    else if (options?.body !== undefined) {headers['Content-Type'] = 'application/json'; body = JSON.stringify(options.body);}
    return (await checked(await fetch(path, {method, body, headers, credentials: 'same-origin'}))).json() as Promise<T>;
  },
  async document(id: number) {
    return (await checked(await fetch(`/api/documents/${id}/download/`, {credentials: 'same-origin'}))).blob();
  }
};
