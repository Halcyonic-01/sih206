import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { StepUpProvider } from './StepUpProvider'

const reply = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

describe('step-up dialog', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('asks for a code, confirms it with the server and lets the blocked action finish', async () => {
    let approvals = 0
    const fetchMock = vi.fn<typeof fetch>(async (url) => {
      if (String(url).includes('/auth/mfa/step-up/')) return reply(200, { verified_recently: true })
      approvals += 1
      return approvals === 1 ? reply(403, { detail: 'Enter a code.', code: 'mfa_step_up_required' }) : reply(200, { ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)
    document.cookie = 'csrftoken=tok; path=/'
    render(<StepUpProvider><p>content</p></StepUpProvider>)
    const result = api('/releases/9/approve', { method: 'POST', json: {} })
    await userEvent.type(await screen.findByLabelText('Authenticator code'), '123456')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    await expect(result).resolves.toEqual({ ok: true })
    const stepUp = fetchMock.mock.calls.find((call) => String(call[0]).includes('/auth/mfa/step-up/'))!
    expect(JSON.parse(String(stepUp[1]!.body))).toEqual({ code: '123456' })
  })

  it('keeps the dialog open with a message when the code is wrong, and rejects on Cancel', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (url) => String(url).includes('/auth/mfa/step-up/')
      ? reply(400, { detail: 'That code is not right.', code: 'invalid_mfa_code' })
      : reply(403, { detail: 'Enter a code.', code: 'mfa_step_up_required' }))
    vi.stubGlobal('fetch', fetchMock)
    render(<StepUpProvider><p>content</p></StepUpProvider>)
    const result = api('/releases/9/issue', { method: 'POST', json: {} })
    const settled = result.catch((error) => error)
    await userEvent.type(await screen.findByLabelText('Authenticator code'), '000000')
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    expect(await screen.findByText('That code is not right.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(async () => expect(await settled).toMatchObject({ code: 'mfa_step_up_required' }))
  })
})
