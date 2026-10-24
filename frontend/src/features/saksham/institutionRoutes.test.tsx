import { Suspense } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from '@/auth/AuthProvider';
import { RequireRole } from '@/auth/RequireRole';
import { routes } from './routes';
import { routeIdentity } from './InstitutionPages';

const user = { id: 1, username: 'synthetic', display_name: 'Synthetic', role: 'institution',
  institution: { id: 1, name: 'Synthetic A', code: 'A' }, unit: null };
const institution = { id: 1, name: 'Synthetic A', code: 'A', version: 1, profile: {
  aicte_id: 'SYNTH-A', trust_name: 'Synthetic trust', region: 'North', state: 'Delhi',
  institution_type: 'PRIVATE', contact_email: 'synthetic@example.invalid', status: 'ACTIVE' } };
const obligation = { id: 1, status: 'UNKNOWN', basis: 'APPROVAL', required_paise: 300000000,
  term_start: '2026-01-01', term_end: '2036-01-01', version: 1, assessment: {
    status: 'UNAVAILABLE', as_of: '2026-10-25', coverage: null, findings: null, holdings: null, open_actions: null } };
const page = (results: unknown[]) => ({ count: results.length, page: 1, page_size: 25, total_pages: 1, results });
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value),
  { status, headers: { 'Content-Type': 'application/json' } });
const fetchMock = vi.fn<typeof fetch>();

function source(overrides: Record<string, () => Response | Promise<Response>> = {}) {
  fetchMock.mockImplementation(async path => {
    const url = String(path);
    if (overrides[url]) return overrides[url]();
    if (url === '/api/auth/me/' || url === '/api/auth/login/') return json(user);
    if (url === '/api/institutions/1') return json(institution);
    if (url.startsWith('/api/institutions?')) return json(page([institution]));
    if (url === '/api/institutions/1/programme-approvals?page=1') return json(page([]));
    if (url === '/api/institutions/1/obligations?page=1') return json(page([obligation]));
    if (url === '/api/obligations/1') return json(obligation);
    if (url === '/api/rules') return json(page([{ id: 1, code: 'synthetic-draft', version: 1 }]));
    if (url === '/api/calculator') return json({ required_paise: 300000000, rule_code: 'synthetic-draft',
      rule_version: 1, source_clause: 'Table 1.4', as_of: '2026-10-25' });
    return json({ code: 'not_found', detail: 'Not found' }, 404);
  });
}

function SameUserLogin() {
  const { login } = useAuth();
  return <button onClick={() => void login('synthetic', 'test-only')}>Same-user login</button>;
}

function mount(path = '/institutions', loginControl = false) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={cache}><AuthProvider>
    {loginControl && <SameUserLogin />}
    <MemoryRouter initialEntries={[path]}><Suspense fallback={<p>Loading route</p>}><Routes>
      {routes.map(route => <Route key={route.path} path={route.path}
        element={<RequireRole roles={route.roles}>{route.element}</RequireRole>} />)}
      <Route path="/login" element={<h1>Sign in required</h1>} />
    </Routes></Suspense></MemoryRouter>
  </AuthProvider></QueryClientProvider>);
}

beforeEach(() => { vi.stubGlobal('fetch', fetchMock); document.cookie = 'csrftoken=p3-test; path=/'; source(); });
afterEach(() => { fetchMock.mockReset(); vi.unstubAllGlobals(); });

describe('institution feature registered in shared auth and routing', () => {
  it('navigates list → real-shaped detail → calculator through shared HTTP', async () => {
    mount();
    const browser = userEvent.setup();
    await browser.click(await screen.findByRole('button', { name: 'Synthetic A' }));
    expect(await screen.findByRole('heading', { name: 'Synthetic A' })).toBeInTheDocument();
    expect(screen.getByText('Synthetic trust')).toBeInTheDocument();
    expect(await screen.findByText(/Coverage unavailable; source integration required/)).toBeInTheDocument();
    expect(screen.getByText('Holding timeline unavailable.')).toBeInTheDocument();
    await browser.click(screen.getByRole('link', { name: 'Requirement calculator' }));
    expect(await screen.findByRole('heading', { name: 'Requirement calculator' })).toBeInTheDocument();
    await browser.selectOptions(await screen.findByLabelText('Rule version'), '1');
    await browser.selectOptions(screen.getByLabelText('Building tenure'), 'LEASED');
    await browser.click(screen.getByRole('button', { name: 'Calculate preview' }));
    expect(await screen.findByText('INR 30,00,000.00')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/calculator', expect.objectContaining({
      body: JSON.stringify({ institution_id: 1, rule_set_id: 1, approvals: [
        { programme: 'MANAGEMENT', level: 'PG', land_tenure: 'OWNED', building_tenure: 'LEASED' }] }),
    }));
    fireEvent.change(screen.getByLabelText('Building tenure'), { target: { value: 'OWNED' } });
    expect(screen.queryByText('INR 30,00,000.00')).not.toBeInTheDocument();
  });

  it.each([400, 403, 404, 409, 503])('shows safe list error %i without fallback data', async status => {
    source({ '/api/institutions?q=&page=1': () => json({ code: 'test', detail: 'test' }, status) });
    mount();
    expect(await screen.findByRole('alert')).toHaveFocus();
    expect(screen.queryByRole('button', { name: 'Synthetic A' })).not.toBeInTheDocument();
  });

  it('shared 401 ends the session and routes to sign-in', async () => {
    source({ '/api/institutions?q=&page=1': () => json({ code: 'not_authenticated', detail: 'Sign in' }, 401) });
    mount();
    expect(await screen.findByRole('heading', { name: 'Sign in required' })).toBeInTheDocument();
  });

  it('does not fetch rules or show a calculator for a foreign parent', async () => {
    mount('/institutions/2/calculator');
    expect(await screen.findByRole('alert')).toHaveTextContent('unavailable');
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/api/rules')).toBe(false);
    expect(screen.queryByRole('button', { name: 'Calculate preview' })).not.toBeInTheDocument();
  });

  it('renders an explicitly empty scoped list', async () => {
    source({ '/api/institutions?q=&page=1': () => json(page([])) });
    mount();
    expect(await screen.findByText('No visible institutions.')).toBeInTheDocument();
  });

  it('invalid route identity cannot issue a source request', () => {
    for (const raw of [undefined, '0', '-1', '1.5', '01', '1e3', '9007199254740992']) expect(routeIdentity(raw)).toBeNull();
    expect(routeIdentity('12')).toBe(12);
  });

  it('same-user login invalidates old requests even when user data is identical', async () => {
    let oldResolve!: (value: Response) => void;
    let reads = 0;
    source({ '/api/institutions?q=&page=1': () => {
      reads++;
      return reads === 1 ? new Promise<Response>(resolve => { oldResolve = resolve; }) :
        json(page([{ ...institution, name: 'Fresh same user' }]));
    } });
    mount('/institutions', true);
    await screen.findByRole('heading', { name: 'Institutions' });
    await userEvent.setup().click(screen.getByRole('button', { name: 'Same-user login' }));
    expect(await screen.findByRole('button', { name: 'Fresh same user' })).toBeInTheDocument();
    await act(async () => oldResolve(json(page([{ ...institution, name: 'Old private data' }]))));
    expect(screen.queryByText('Old private data')).not.toBeInTheDocument();
  });
});
