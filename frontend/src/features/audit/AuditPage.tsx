import { Card, Tabs } from 'antd'
import { PageHeader } from '@/components/PageHeader'
import AccessLogTab from './AccessLogTab'
import AuditTrailTab from './AuditTrailTab'
import IntegrityTab from './IntegrityTab'

export default function AuditPage() {
  return (
    <>
      <PageHeader title="Audit and access" subtitle="Every change to a record, and every sign-in, download and export. Read-only." />
      <Card>
        <Tabs destroyInactiveTabPane items={[
          { key: 'trail', label: 'Audit trail', children: <AuditTrailTab /> },
          { key: 'access', label: 'Access log', children: <AccessLogTab /> },
          { key: 'integrity', label: 'Integrity', children: <IntegrityTab /> },
        ]} />
      </Card>
    </>
  )
}
