import { t as tr, useLanguage } from '@/i18n';
import { BellOutlined } from '@ant-design/icons'
import { Badge, Button, Divider, Flex, List, Popover, Typography } from 'antd'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, LoadingState, QueryError } from '@/components/states'
import { useMarkAllRead, useMarkRead, useNotifications, useUnreadCount } from './api'
import { NotificationItem } from './NotificationItem'

/** Header bell: unread badge (polled every 30 s) and the latest notifications in a popover. */
export default function Bell() {
  useLanguage();
  const [open, setOpen] = useState(false)
  const unread = useUnreadCount()
  const latest = useNotifications({ pageSize: 6 }, open)
  const markRead = useMarkRead()
  const markAll = useMarkAllRead()
  const count = unread.data ?? 0

  const content = (
    <div style={{ width: 360, maxWidth: 'calc(100vw - 48px)' }}>
      {latest.isPending ? <LoadingState rows={2} />
        : latest.isError ? <QueryError error={latest.error} onRetry={() => void latest.refetch()} />
        : latest.data.results.length === 0 ? <EmptyState title={tr("No notifications yet")} />
        : (
          <List size="small" dataSource={latest.data.results}
                renderItem={(item) => (
                  <List.Item style={{ paddingInline: 0 }}>
                    <NotificationItem item={item} compact onRead={(id) => markRead.mutate(id)} />
                  </List.Item>
                )} />
        )}
      <Divider style={{ margin: '8px 0' }} />
      <Flex justify="space-between">
        <Button size="small" type="link" disabled={count === 0 || markAll.isPending}
                onClick={() => markAll.mutate()}>{tr("Mark all read")}</Button>
        <Link to="/notifications" onClick={() => setOpen(false)}>{tr("View all")}</Link>
      </Flex>
    </div>
  )

  return (
    <Popover content={content} trigger="click" open={open} onOpenChange={setOpen} placement="bottomRight"
             title={<Typography.Text strong>{tr("Notifications")}</Typography.Text>}>
      <Badge count={count} size="small" overflowCount={99}>
        <Button type="text" shape="circle" size="large" icon={<BellOutlined />}
                aria-label={count ? tr('Notifications, {count} unread', {count}) : tr("Notifications")} />
      </Badge>
    </Popover>
  )
}
