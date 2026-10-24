import { Button, Card, List, Segmented } from 'antd'
import { useState } from 'react'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState, LoadingState, QueryError } from '@/components/states'
import { useMarkAllRead, useMarkRead, useNotifications, useUnreadCount } from './api'
import { NotificationItem } from './NotificationItem'

export default function InboxPage() {
  const [filter, setFilter] = useState<'all' | 'unread'>('all')
  const [page, setPage] = useState(1)
  const list = useNotifications({ unread: filter === 'unread', page, pageSize: 20 })
  const unread = useUnreadCount()
  const markRead = useMarkRead()
  const markAll = useMarkAllRead()

  return (
    <>
      <PageHeader title="Notifications" subtitle="Reminders, review results and alerts for your account."
                  extra={<Button onClick={() => markAll.mutate()} disabled={!unread.data || markAll.isPending}>
                    Mark all as read
                  </Button>} />
      <Card>
        <Segmented style={{ marginBottom: 16 }} value={filter} options={[
          { label: 'All', value: 'all' }, { label: `Unread${unread.data ? ` (${unread.data})` : ''}`, value: 'unread' },
        ]} onChange={(value) => { setFilter(value as 'all' | 'unread'); setPage(1) }} />
        {list.isPending ? <LoadingState />
          : list.isError ? <QueryError error={list.error} onRetry={() => void list.refetch()} />
          : (
            <List dataSource={list.data.results} locale={{ emptyText: (
              <EmptyState title={filter === 'unread' ? 'You are all caught up' : 'No notifications yet'}
                          detail="New reminders and review updates will appear here." />
            ) }}
                  pagination={{ current: page, pageSize: 20, total: list.data.count, onChange: setPage,
                                hideOnSinglePage: true, showSizeChanger: false }}
                  renderItem={(item) => (
                    <List.Item><NotificationItem item={item} onRead={(id) => markRead.mutate(id)} /></List.Item>
                  )} />
          )}
      </Card>
    </>
  )
}
