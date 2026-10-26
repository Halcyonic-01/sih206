import { Alert, Button, Form, Input, Typography } from 'antd'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, post } from '@/api/client'
import { ME_KEY, useAuth } from '@/auth/AuthProvider'
import type { CurrentUser } from '@/auth/types'
import { PageHeader } from '@/components/PageHeader'
import { Panel } from '@/components/Panel'

interface Setup { secret: string; otpauth_uri: string; issuer: string }

/** Turn two-factor sign-in on or off for the signed-in staff member. The secret is shown for typing into the authenticator
 * app (and as an otpauth link for apps that open it); there is no QR code in this prototype. */
export default function SecurityPage() {
  const { user } = useAuth()
  const client = useQueryClient()
  const [setup, setSetup] = useState<Setup | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [form] = Form.useForm<{ code: string }>()
  const mfa = user?.mfa

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError(null)
    setDone(null)
    try { await action() } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Cannot reach the server. Try again.')
    } finally { setBusy(false) }
  }

  const start = () => run(async () => { setSetup(await post<Setup>('/auth/mfa/setup/')); form.resetFields() })
  const confirm = (values: { code: string }) => run(async () => {
    const me = await post<CurrentUser>('/auth/mfa/confirm/', { code: values.code })
    client.setQueryData(ME_KEY, me)
    setSetup(null)
    setDone('Two-factor sign-in is on. You will be asked for a code each time you sign in.')
  })
  const disable = (values: { code: string }) => run(async () => {
    await post('/auth/mfa/disable/', { code: values.code })
    await client.invalidateQueries({ queryKey: ME_KEY })
    setDone('Two-factor sign-in is off.')
    form.resetFields()
  })

  if (!mfa?.in_scope) return <Alert type="info" showIcon message="Two-factor sign-in is available to staff accounts." />

  return (
    <section>
      <PageHeader title="Two-factor sign-in" subtitle="A code from an authenticator app, in addition to your password." />
      {mfa.required && !mfa.enrolled && (
        <Alert type="warning" showIcon style={{ marginBottom: 16 }} message="Set this up to continue"
               description="Two-factor sign-in is required for your role. The rest of the portal opens once it is on." />
      )}
      {error && <Alert type="error" showIcon role="alert" message={error} style={{ marginBottom: 16 }} />}
      {done && <Alert type="success" showIcon message={done} style={{ marginBottom: 16 }} />}
      <Panel title={mfa.enrolled ? 'Two-factor sign-in is on' : 'Two-factor sign-in is off'}>
        {!mfa.enrolled && !setup && (
          <>
            <p>Release authorisation, letter issue, completion and officer corrections will also ask for a fresh code.</p>
            <Button type="primary" loading={busy} onClick={() => void start()}>Set up an authenticator app</Button>
          </>
        )}
        {setup && (
          <div className="stack">
            <ol>
              <li>Open an authenticator app (Google Authenticator, Microsoft Authenticator, Authy, 1Password…).</li>
              <li>Add an account and choose <strong>enter a setup key</strong>. Account: your username. Key:
                {' '}<Typography.Text code copyable aria-label="Setup key">{setup.secret}</Typography.Text></li>
              <li>Enter the 6-digit code the app shows, below.</li>
            </ol>
            <p className="muted">On a phone you can also open <a href={setup.otpauth_uri}>this setup link</a> in the app.</p>
            <Form form={form} layout="vertical" onFinish={confirm} requiredMark={false} disabled={busy} style={{ maxWidth: 320 }}>
              <Form.Item name="code" label="Authenticator code" rules={[{ required: true, message: 'Enter the 6-digit code.' }]}>
                <Input inputMode="numeric" autoComplete="one-time-code" maxLength={8} />
              </Form.Item>
              <Button type="primary" htmlType="submit" loading={busy}>Turn on</Button>
            </Form>
          </div>
        )}
        {mfa.enrolled && !mfa.required && (
          <Form form={form} layout="vertical" onFinish={disable} requiredMark={false} disabled={busy} style={{ maxWidth: 320 }}>
            <p>To turn it off, enter a current code.</p>
            <Form.Item name="code" label="Authenticator code" rules={[{ required: true, message: 'Enter the 6-digit code.' }]}>
              <Input inputMode="numeric" autoComplete="one-time-code" maxLength={8} />
            </Form.Item>
            <Button danger htmlType="submit" loading={busy}>Turn off</Button>
          </Form>
        )}
        {mfa.enrolled && mfa.required && <p>It is required for your role and cannot be turned off here. If you lose your phone, ask the portal owner to reset it.</p>}
      </Panel>
    </section>
  )
}
