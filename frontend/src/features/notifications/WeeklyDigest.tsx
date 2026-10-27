import { useMutation, useQuery } from '@tanstack/react-query'
import { Button, Card, Checkbox, Space, Typography } from 'antd'
import { get, patch } from '@/api/client'
import { LoadingState, QueryError } from '@/components/states'
import { t as tr, useLanguage } from '@/i18n'

interface Preference { enabled: boolean; version: number; dispatch_enabled: boolean }
interface Preview { eligible: boolean; reason?: string; body?: string }

export default function WeeklyDigest() {
  useLanguage()
  const preference = useQuery({queryKey: ['weekly-digest', 'preference'],
    queryFn: () => get<Preference>('/notifications/digest-preference/'), retry: false})
  const preview = useQuery({queryKey: ['weekly-digest', 'preview'],
    queryFn: () => get<Preview>('/notifications/digest-preview/'), enabled: false, retry: false})
  const save = useMutation({mutationFn: (enabled: boolean) => patch<Preference>('/notifications/digest-preference/',
    {enabled, version: preference.data?.version}), onSuccess: () => { void preference.refetch() }})
  return <Card title={tr('Weekly email digest')} style={{marginBottom: 16}}>
    <Typography.Paragraph>{tr('Monday 09:00 IST. Email summaries are in English. Individual workflow alerts remain enabled.')}</Typography.Paragraph>
    {preference.isPending ? <LoadingState /> : preference.isError
      ? <QueryError error={preference.error} onRetry={() => void preference.refetch()} />
      : <Space direction="vertical">
        <Checkbox checked={preference.data.enabled} disabled={save.isPending}
          onChange={event => save.mutate(event.target.checked)}>{tr('Receive weekly email digest')}</Checkbox>
        <Typography.Text>{preference.data.dispatch_enabled ? tr('Digest dispatch enabled') : tr('Digest dispatch is disabled on this server')}</Typography.Text>
        <Button loading={preview.isFetching} onClick={() => void preview.refetch()}>{tr('Preview my digest')}</Button>
      </Space>}
    {save.isError && <QueryError error={save.error} onRetry={() => {save.reset(); void preference.refetch()}} />}
    {preview.isError && <QueryError error={preview.error} onRetry={() => void preview.refetch()} />}
    {preview.data && <pre style={{whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'}}>
      {preview.data.eligible ? preview.data.body : tr('Digest unavailable: no eligible email or preference is disabled.')}
    </pre>}
  </Card>
}
