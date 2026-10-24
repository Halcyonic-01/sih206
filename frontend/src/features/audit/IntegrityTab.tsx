import { SafetyCertificateOutlined } from '@ant-design/icons'
import { Alert, Button, List, Typography } from 'antd'
import { QueryError } from '@/components/states'
import { useVerifyChain } from './api'

const REASONS: Record<string, string> = {
  event_modified: 'Event was changed after it was recorded',
  event_missing: 'Event was removed',
  chain_break: 'A link before this event is missing or was inserted',
}

export default function IntegrityTab() {
  const verify = useVerifyChain()
  const result = verify.data
  return (
    <>
      <Typography.Paragraph>
        Every audit event is sealed into a keyed hash chain when it is written. Verifying recomputes the whole chain:
        an event that was edited, removed or slipped in behind the application shows up as broken.
      </Typography.Paragraph>
      <Button type="primary" icon={<SafetyCertificateOutlined />} loading={verify.isPending} onClick={() => verify.mutate()}>
        Verify chain
      </Button>
      <div style={{ marginTop: 16 }}>
        {verify.isError && <QueryError error={verify.error} onRetry={() => verify.mutate()} />}
        {result?.status === 'ok' && (
          <Alert type="success" showIcon message="Chain verified"
                 description={<>{result.checked} events sealed{result.backfilled > 0 && `, ${result.backfilled} of them sealed late because they existed before sealing was switched on`}.
                   {result.head && <> Head: <code>{result.head.slice(0, 16)}…</code></>}</>} />
        )}
        {result?.status === 'incomplete' && (
          <Alert type="warning" showIcon message={`${result.unsealed} event(s) have no seal`}
                 description="They were added without going through the application. Run seal_audit_chain, then investigate how they were created." />
        )}
        {result?.status === 'broken' && (
          <Alert type="error" showIcon message="Chain broken: the audit trail does not match its seals"
                 description={<List size="small" dataSource={result.broken}
                   renderItem={(item) => <List.Item>Event #{item.event_id}: {REASONS[item.reason] ?? item.reason}</List.Item>} />} />
        )}
      </div>
    </>
  )
}
