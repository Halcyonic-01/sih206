import { t as tr, useLanguage } from '@/i18n';
import { Button, Flex, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import { Link } from 'react-router-dom'
import { safeLink, type AppNotification } from './api'

dayjs.extend(relativeTime)

export function NotificationItem({ item, onRead, compact = false }: {
  item: AppNotification
  onRead: (id: number) => void
  compact?: boolean
}) {
  const language = useLanguage();
  const message = language === 'hi' ? item.translations?.hi : undefined;
  const target = safeLink(item.link)
  return (
    <div className={`note-row${item.is_read ? ' note-row--read' : ''}`}>
      <span className={`note-dot${item.is_read ? ' note-dot--read' : ''}`} role="img" aria-label={item.is_read ? tr("Read") : tr("Unread")} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <Flex gap={8} align="center" wrap>
          <Typography.Text strong={!item.is_read}>{message?.subject ?? item.subject}</Typography.Text>
          {item.severity !== 'info' && <Tag bordered={false} className={`tag tag--${item.severity === 'critical' ? 'danger' : 'warning'}`}>{tr(item.severity)}</Tag>}
        </Flex>
        {!compact && <Typography.Paragraph style={{ margin: '4px 0' }}>{message?.body ?? item.body}</Typography.Paragraph>}
        <Typography.Text type="secondary" style={{ fontSize: 12 }} title={dayjs(item.created_at).format('D MMM YYYY, HH:mm')}>
          {dayjs(item.created_at).fromNow()}
        </Typography.Text>
      </div>
      <Flex gap={4} wrap justify="end" className="note-actions">
        {target && (
          <Link to={target} onClick={() => !item.is_read && onRead(item.id)}>{tr("Open")}</Link>
        )}
        {!item.is_read && <Button size="small" type="text" onClick={() => onRead(item.id)}>{tr("Mark read")}</Button>}
      </Flex>
    </div>
  )
}
