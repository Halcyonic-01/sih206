import { t as tr, useLanguage } from '@/i18n';
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
  useLanguage();
  const verify = useVerifyChain()
  const result = verify.data
  return (
    <>
      <Typography.Paragraph>
        {tr("Each audit event is sealed into a keyed hash chain when it is written. Verifying recomputes the whole chain, so an event that was edited, removed or added outside the application shows up as broken.")}</Typography.Paragraph>
      <Button type="primary" icon={<SafetyCertificateOutlined />} loading={verify.isPending} onClick={() => verify.mutate()}>
        {tr("Verify chain")}</Button>
      <div style={{ marginTop: 16 }}>
        {verify.isError && <QueryError error={verify.error} onRetry={() => verify.mutate()} />}
        {result?.status === 'ok' && (
          <Alert type="success" showIcon message={tr("Chain verified")}
                 description={<>{result.checked} {tr("  events sealed")}{result.backfilled > 0 && tr(", {0} of them sealed late because they existed before sealing was switched on", {"0": (result.backfilled)})}.
                   {result.head && <> {tr("  Head:  ")}<code>{result.head.slice(0, 16)}…</code></>}</>} />
        )}
        {result?.status === 'incomplete' && (
          <Alert type="warning" showIcon message={tr("{0} event(s) have no seal", {"0": (result.unsealed)})}
                 description={tr("They were added without going through the application. Run seal_audit_chain, then investigate how they were created.")} />
        )}
        {result?.status === 'broken' && (
          <Alert type="error" showIcon message={tr("Chain broken: the audit trail does not match its seals")}
                 description={<List size="small" dataSource={result.broken}
                   renderItem={(item) => <List.Item>{tr("Event #")}{item.event_id}: {REASONS[item.reason] ?? item.reason}</List.Item>} />} />
        )}
      </div>
    </>
  )
}
