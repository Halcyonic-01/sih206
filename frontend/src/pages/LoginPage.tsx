import { LockOutlined, UserOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { applyFieldErrors } from '@/api/forms'
import { useAuth } from '@/auth/AuthProvider'

interface LoginValues { username: string; password: string }

export default function LoginPage() {
  const { user, status, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form] = Form.useForm<LoginValues>()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const destination = (location.state as { from?: string } | null)?.from ?? '/'

  if (status === 'authenticated' && user) return <Navigate to={destination} replace />

  async function submit(values: LoginValues) {
    setBusy(true)
    setError(null)
    try {
      await login(values.username.trim(), values.password)
      navigate(destination, { replace: true })
    } catch (caught) {
      if (applyFieldErrors(form, caught)) return
      setError(caught instanceof ApiError ? caught.message : 'Cannot reach the server. Try again.')
      form.setFieldValue('password', '')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-page">
      <Card className="login-card">
        <Typography.Title level={3} style={{ marginTop: 0 }}>Pramaan</Typography.Title>
        <Typography.Paragraph type="secondary">
          Trust Backed by Evidence · AICTE security deposit portal. Sign in with the account issued to you.
        </Typography.Paragraph>
        {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} role="alert" />}
        <Form form={form} layout="vertical" onFinish={submit} requiredMark={false} disabled={busy}>
          <Form.Item name="username" label="Username" rules={[{ required: true, message: 'Enter your username.' }]}>
            <Input prefix={<UserOutlined />} autoComplete="username" autoFocus />
          </Form.Item>
          <Form.Item name="password" label="Password" rules={[{ required: true, message: 'Enter your password.' }]}>
            <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={busy}>Sign in</Button>
        </Form>
        <Typography.Paragraph type="secondary" style={{ margin: '16px 0 0', fontSize: 12 }}>
          After five failed attempts the account is locked for a short time.
        </Typography.Paragraph>
      </Card>
    </main>
  )
}
