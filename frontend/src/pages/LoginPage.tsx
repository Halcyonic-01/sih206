import { t as tr, useLanguage } from '@/i18n';
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

/** Resume an interrupted session only if the account signing in may open the requested page.
 * Explicit sign-out clears that destination in RequireRole, so the next login starts at home. */
export function allowedDestination(destination: string, role: string | null | undefined): string {
  const pathname = destination.split(/[?#]/)[0] ?? '/'
  const route = appRoutes.find((entry) => matchPath({ path: entry.path, end: true }, pathname))
  if (!route?.roles) return destination
  return role && route.roles.includes(role as never) ? destination : '/'
}

export default function LoginPage() {
  useLanguage();
  const { user, status, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form] = Form.useForm<LoginValues>()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const destination = (location.state as { from?: string } | null)?.from ?? '/'

  if (status === 'authenticated' && user) return <Navigate to={allowedDestination(destination, user.role)} replace />

  async function submit(values: LoginValues) {
    setBusy(true)
    setError(null)
    try {
      const signedIn = await login(values.username.trim(), values.password)
      navigate(allowedDestination(destination, signedIn.role), { replace: true })
    } catch (caught) {
      if (applyFieldErrors(form, caught)) return
      setError(caught instanceof ApiError ? caught.message : 'Cannot reach the server. Try again.')
      form.setFieldValue('password', '')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <a className="skip-link" href="#sign-in">{tr("Skip to sign in")}</a>
      <header className="portal-masthead"><PortalIdentity /></header>
      <div className="service-bar"><span className="service-bar__name">{tr("Security Deposit Management")}</span>
        <span className="service-bar__context">{tr("Institution & officer access")}</span></div>
      <main className="auth-layout">
        <section className="auth-introduction" aria-label={tr("About the portal")}>
          <span className="eyebrow">{tr("ONE PORTAL. A CLEARER PROCESS.")}</span>
          <h2>{tr("Every deposit.")}{' '}<br />{tr("Every decision.")}{' '}<br /><em>{tr("Accounted for.")}</em></h2>
          <p className="auth-lead">{tr("A shared workspace for institutions and reviewing teams to manage security deposits, supporting evidence and the next action.")}</p>
          <p className="prototype-note">{tr("Independent student prototype. No official AICTE endorsement is implied.")}</p>
        </section>
        <section className="auth-main" aria-labelledby="sign-in">
          <div className="auth-card">
            <span className="eyebrow">{tr("ACCESS YOUR WORKSPACE")}</span>
            <h1 id="sign-in" tabIndex={-1}>{tr("Sign in")}</h1>
            <p className="muted">{tr("Use the account issued to your institution or office.")}</p>
            {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} role="alert" />}
            <Form form={form} layout="vertical" size="large" onFinish={submit} requiredMark={false} disabled={busy}>
              <Form.Item name="username" label={tr("Username")} rules={[{ required: true, message: tr("Enter your username.") }]}>
                <Input prefix={<UserOutlined aria-hidden />} autoComplete="username" autoFocus />
              </Form.Item>
              <Form.Item name="password" label={tr("Password")} rules={[{ required: true, message: tr("Enter your password.") }]}>
                <Input.Password prefix={<LockOutlined aria-hidden />} autoComplete="current-password" />
              </Form.Item>
              <Button type="primary" htmlType="submit" block loading={busy}>{tr("Sign in")}</Button>
            </Form>
            <p className="auth-help"><LockOutlined aria-hidden /> {tr("  Access is limited to your assigned role and institution.")}</p>
            <div className="auth-security-note">{tr("After five failed attempts the account is locked for a few minutes. Contact your project administrator if you need account access.")}</div>
          </div>
          <p className="auth-foot">{tr("Acceptance of a deposit record is for tracking and is not verification by the bank.")}</p>
        </section>
      </main>
      <PortalFooter />
    </div>
  )
}
