import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Form, Input } from 'antd'
import { useState } from 'react'
import { matchPath, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { applyFieldErrors } from '@/api/forms'
import { useAuth } from '@/auth/AuthProvider'
import { Brand } from '@/components/Logo'
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
    <main className="auth-page">
      <aside className="auth-aside" aria-label="About the portal">
        <Brand inverse size={44} />
        <div>
          <h2>Security deposits, tracked from submission to release</h2>
          <p>One place for institutions and AICTE officers to record, review and follow every deposit.</p>
          <ul className="auth-points">
            <li>FDR, RTGS and RPGF deposits with their supporting documents</li>
            <li>Reminders before maturity and follow-up on overdue items</li>
            <li>A complete, tamper-evident record of every change</li>
          </ul>
        </div>
        <small>All India Council for Technical Education</small>
      </aside>
      <div className="auth-main">
        <div className="auth-mobile-brand"><Brand size={42} /></div>
        <div className="auth-card">
          <h1>Sign in</h1>
          <p className="muted">Use the account issued to your institution or office.</p>
          {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} role="alert" />}
          <Form form={form} layout="vertical" size="large" onFinish={submit} requiredMark={false} disabled={busy}>
            <Form.Item name="username" label="Username" rules={[{ required: true, message: 'Enter your username.' }]}>
              <Input prefix={<UserOutlined aria-hidden />} autoComplete="username" autoFocus />
            </Form.Item>
            <Form.Item name="password" label="Password" rules={[{ required: true, message: 'Enter your password.' }]}>
              <Input.Password prefix={<LockOutlined aria-hidden />} autoComplete="current-password" />
            </Form.Item>
            <Button type="primary" htmlType="submit" block loading={busy}>Sign in</Button>
          </Form>
          <p className="auth-help">After five failed attempts the account is locked for a few minutes.</p>
        </div>
        <p className="auth-foot">Acceptance of a deposit record is for tracking and is not verification by the bank.</p>
      </div>
    </main>
  )
}
