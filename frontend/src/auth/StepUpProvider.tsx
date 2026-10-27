import { Alert, Form, Input, Modal } from 'antd'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { ApiError, post, setStepUpHandler } from '@/api/client'

interface Waiting { resolve: () => void; reject: () => void }

/** Asks for an authenticator code when the server wants a recent one before a consequential action
 * (release authorisation, letter issue, completion, officer correction), then lets the action continue. */
export function StepUpProvider({ children }: { children: ReactNode }) {
  const [waiting, setWaiting] = useState<Waiting | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [form] = Form.useForm<{ code: string }>()
  const current = useRef<Waiting | null>(null)

  const ask = useCallback(() => new Promise<void>((resolve, reject) => {
    // A second action waiting at the same time shares the one dialog.
    if (current.current) { const first = current.current; current.current = { resolve: () => { first.resolve(); resolve() }, reject: () => { first.reject(); reject() } }; setWaiting(current.current); return }
    current.current = { resolve, reject }
    setError(null)
    form.resetFields()
    setWaiting(current.current)
  }), [form])

  useEffect(() => setStepUpHandler(ask), [ask])

  function finish(ok: boolean) {
    const pending = current.current
    current.current = null
    setWaiting(null)
    if (pending) ok ? pending.resolve() : pending.reject()
  }

  async function submit(values: { code: string }) {
    setBusy(true)
    setError(null)
    try {
      await post('/auth/mfa/step-up/', { code: values.code })
      finish(true)
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Cannot reach the server. Try again.')
      form.setFieldValue('code', '')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {children}
      <Modal open={waiting !== null} title="Confirm it is you" okText="Confirm" cancelText="Cancel" confirmLoading={busy}
             onOk={() => form.submit()} onCancel={() => finish(false)} destroyOnHidden maskClosable={false}>
        <p>This action needs a fresh code. Open your authenticator app and enter the 6-digit code.</p>
        {error && <Alert type="error" showIcon message={error} role="alert" style={{ marginBottom: 12 }} />}
        <Form form={form} layout="vertical" onFinish={submit} requiredMark={false}>
          <Form.Item name="code" label="Authenticator code" rules={[{ required: true, message: 'Enter the 6-digit code.' }]}>
            <Input inputMode="numeric" autoComplete="one-time-code" maxLength={8} autoFocus />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
