import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Form, Input } from 'antd'
import { useState } from 'react'
import { matchPath, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { applyFieldErrors } from '@/api/forms'
import { useAuth } from '@/auth/AuthProvider'
import { PortalFooter, PortalIdentity } from '@/components/PortalChrome'
import { appRoutes } from '@/routes/registry'

interface LoginValues { username: string; password: string }

/** Return to the page that asked for sign-in only if the account now signing in may open it. After a sign-out the
 * previous user's page is remembered too, and a different role would otherwise land on an access-denied screen. */
export function allowedDestination(destination: string, role: string | null | undefined): string {
  const pathname = destination.split(/[?#]/)[0] ?? '/'
  const route = appRoutes.find((entry) => matchPath({ path: entry.path, end: true }, pathname))
  if (!route?.roles) return destination
  return role && route.roles.includes(role as never) ? destination : '/'
}

export default function LoginPage() {
  const { user, status, login, verifyMfa } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form] = Form.useForm<LoginValues>()
  const [codeForm] = Form.useForm<{ code: string }>()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [needsCode, setNeedsCode] = useState(false)
  const destination = (location.state as { from?: string } | null)?.from ?? '/'

  if (status === 'authenticated' && user) return <Navigate to={allowedDestination(destination, user.role)} replace />

  async function submit(values: LoginValues) {
    setBusy(true)
    setError(null)
    try {
      const result = await login(values.username.trim(), values.password)
      if ('mfa_required' in result) { setNeedsCode(true); return }
      navigate(allowedDestination(destination, result.role), { replace: true })
    } catch (caught) {
      if (applyFieldErrors(form, caught)) return
      setError(caught instanceof ApiError ? caught.message : 'Cannot reach the server. Try again.')
      form.setFieldValue('password', '')
    } finally {
      setBusy(false)
    }
  }

  async function submitCode(values: { code: string }) {
    setBusy(true)
    setError(null)
    try {
      const signedIn = await verifyMfa(values.code)
      navigate(allowedDestination(destination, signedIn.role), { replace: true })
    } catch (caught) {
      const expired = caught instanceof ApiError && caught.code === 'mfa_pending_expired'
      if (expired) setNeedsCode(false)
      setError(caught instanceof ApiError ? caught.message : 'Cannot reach the server. Try again.')
      codeForm.setFieldValue('code', '')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <a className="skip-link" href="#sign-in">Skip to sign in</a>
      <header className="portal-masthead"><PortalIdentity /></header>
      <div className="service-bar"><span className="service-bar__name">Security Deposit Management</span>
        <span className="service-bar__context">Institution &amp; officer access</span></div>
      <main className="auth-layout">
        <section className="auth-introduction" aria-label="About the portal">
          <span className="eyebrow">ONE PORTAL. A CLEARER PROCESS.</span>
          <h2>Every deposit.{' '}<br />Every decision.{' '}<br /><em>Accounted for.</em></h2>
          <p className="auth-lead">A shared workspace for institutions and reviewing teams to manage
            security deposits, supporting evidence and the next action.</p>
          <p className="prototype-note">Independent student prototype. No official AICTE endorsement is implied.</p>
        </section>
        <section className="auth-main" aria-labelledby="sign-in">
          <div className="auth-card">
            <span className="eyebrow">ACCESS YOUR WORKSPACE</span>
            <h1 id="sign-in" tabIndex={-1}>{needsCode ? 'Enter your code' : 'Sign in'}</h1>
            <p className="muted">{needsCode ? 'Open your authenticator app and enter the 6-digit code for this portal.'
              : 'Use the account issued to your institution or office.'}</p>
            {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} role="alert" />}
            {needsCode ? (
              <Form form={codeForm} layout="vertical" size="large" onFinish={submitCode} requiredMark={false} disabled={busy}>
                <Form.Item name="code" label="Authenticator code" rules={[{ required: true, message: 'Enter the 6-digit code.' }]}>
                  <Input inputMode="numeric" autoComplete="one-time-code" maxLength={8} autoFocus />
                </Form.Item>
                <Button type="primary" htmlType="submit" block loading={busy}>Verify and sign in</Button>
                <Button type="link" block onClick={() => { setNeedsCode(false); setError(null) }}>Use a different account</Button>
              </Form>
            ) : (
            <Form form={form} layout="vertical" size="large" onFinish={submit} requiredMark={false} disabled={busy}>
              <Form.Item name="username" label="Username" rules={[{ required: true, message: 'Enter your username.' }]}>
                <Input prefix={<UserOutlined aria-hidden />} autoComplete="username" autoFocus />
              </Form.Item>
              <Form.Item name="password" label="Password" rules={[{ required: true, message: 'Enter your password.' }]}>
                <Input.Password prefix={<LockOutlined aria-hidden />} autoComplete="current-password" />
              </Form.Item>
              <Button type="primary" htmlType="submit" block loading={busy}>Sign in</Button>
            </Form>
            )}
            <p className="auth-help"><LockOutlined aria-hidden /> Access is limited to your assigned role and institution.</p>
            <div className="auth-security-note">After five failed attempts the account is locked for a few minutes.
              Contact your project administrator if you need account access.</div>
          </div>
          <p className="auth-foot">Acceptance of a deposit record is for tracking and is not verification by the bank.</p>
        </section>
      </main>
      <PortalFooter />
    </div>
  )
}
