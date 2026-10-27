import { t as tr, useLanguage } from '@/i18n';
import { Card, Tabs } from 'antd'
import { PageHeader } from '@/components/PageHeader'
import AccessLogTab from './AccessLogTab'
import AuditTrailTab from './AuditTrailTab'
import IntegrityTab from './IntegrityTab'

export default function AuditPage() {
  useLanguage();
  return (
    <>
      <PageHeader title={tr("Audit and access")} subtitle={tr("Every change to a record, and every sign-in, download and export. Read-only.")} />
      <Card>
        <Tabs destroyInactiveTabPane items={[
          { key: 'trail', label: tr("Audit trail"), children: <AuditTrailTab /> },
          { key: 'access', label: tr("Access log"), children: <AccessLogTab /> },
          { key: 'integrity', label: tr("Integrity"), children: <IntegrityTab /> },
        ]} />
      </Card>
    </>
  )
}
