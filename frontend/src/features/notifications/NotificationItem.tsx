import { Button, Flex, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import { Link } from 'react-router-dom'
import { safeLink, type AppNotification } from './api'

dayjs.extend(relativeTime)

const COLORS = { info: 'blue', warning: 'orange', critical: 'red' } as const

export function NotificationItem({ item, onRead, compact = false }: {
  item: AppNotification
  onRead: (id: number) => void
  compact?: boolean
}) {
  const target = safeLink(item.link)
  return (
    <Flex gap={12} align="start" style={{ opacity: item.is_read ? 0.7 : 1 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Flex gap={8} align="center" wrap>
          {!item.is_read && <span aria-label="Unread" style={{ width: 8, height: 8, borderRadius: 4, background: '#1d3f72' }} />}
          <Typography.Text strong={!item.is_read}>{item.subject}</Typography.Text>
          {item.severity !== 'info' && <Tag color={COLORS[item.severity]}>{item.severity}</Tag>}
        </Flex>
        {!compact && <Typography.Paragraph style={{ margin: '4px 0' }}>{item.body}</Typography.Paragraph>}
        <Typography.Text type="secondary" style={{ fontSize: 12 }} title={dayjs(item.created_at).format('D MMM YYYY, HH:mm')}>
          {dayjs(item.created_at).fromNow()}
        </Typography.Text>
      </div>
      <Flex gap={4} wrap>
        {target && (
          <Link to={target} onClick={() => !item.is_read && onRead(item.id)}>
            <Button size="small" type="link">Open</Button>
          </Link>
        )}
        {!item.is_read && <Button size="small" type="text" onClick={() => onRead(item.id)}>Mark read</Button>}
      </Flex>
    </Flex>
  )
}
