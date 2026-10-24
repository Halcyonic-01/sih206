import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import LoginPage from '@/pages/LoginPage'
import { AuthProvider } from './AuthProvider'
import { RequireRole } from './RequireRole'

const fetchMock = vi.fn<typeof fetch>()
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
})
const officer = { id: 1, username: 'officer', display_name: 'Officer', role: 'officer', institution: null }

function mount(initial: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <MemoryRouter initialEntries={[initial]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/officer-only" element={<RequireRole roles={['officer']}><p>Officer screen</p></RequireRole>} />
            <Route path="/authority-only" element={<RequireRole roles={['authority']}><p>Authority screen</p></RequireRole>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

beforeEach(() => { vi.stubGlobal('fetch', fetchMock) })
afterEach(() => { fetchMock.mockReset(); vi.unstubAllGlobals() })

describe('RequireRole', () => {
  it('sends anonymous visitors to the login page', async () => {
    fetchMock.mockImplementation(async () => json(401, { detail: 'Auth.', code: 'not_authenticated' }))
    mount('/officer-only')
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.queryByText('Officer screen')).not.toBeInTheDocument()
  })

  it('renders the screen for an allowed role', async () => {
    fetchMock.mockImplementation(async () => json(200, officer))
    mount('/officer-only')
    expect(await screen.findByText('Officer screen')).toBeInTheDocument()
  })

  it('shows a 403 state for another role', async () => {
    fetchMock.mockImplementation(async () => json(200, officer))
    mount('/authority-only')
    expect(await screen.findByText('Not available for your role')).toBeInTheDocument()
    expect(screen.queryByText('Authority screen')).not.toBeInTheDocument()
  })

  it('explains an account with no portal role', async () => {
    fetchMock.mockImplementation(async () => json(200, { ...officer, role: null }))
    mount('/officer-only')
    expect(await screen.findByText('No portal role assigned')).toBeInTheDocument()
  })

  it('signs in from the login page and lands on the requested screen', async () => {
    fetchMock.mockImplementation(async (url, init) => {
      const path = String(url)
      if (path === '/api/auth/me/') return json(401, { detail: 'Auth.', code: 'not_authenticated' })
      if (path === '/api/auth/login/' && init?.method === 'POST') return json(200, officer)
      return json(404, { detail: 'Not found.', code: 'not_found' })
    })
    document.cookie = 'csrftoken=tok; path=/'
    mount('/officer-only')
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Username'), 'officer')
    await user.type(screen.getByLabelText('Password'), 'secret-password')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => expect(screen.getByText('Officer screen')).toBeInTheDocument())
  })

  it('shows the lockout message from the server and clears the password', async () => {
    fetchMock.mockImplementation(async (url) => {
      if (String(url) === '/api/auth/me/') return json(401, { detail: 'Auth.', code: 'not_authenticated' })
      return json(429, { detail: 'Too many failed sign-in attempts. Wait before trying again.', code: 'locked_out' })
    })
    document.cookie = 'csrftoken=tok; path=/'
    mount('/login')
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Username'), 'officer')
    await user.type(screen.getByLabelText('Password'), 'x')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many failed sign-in attempts')
    expect(screen.getByLabelText('Password')).toHaveValue('')
  })
})
