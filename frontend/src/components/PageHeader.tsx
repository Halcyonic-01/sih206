import { Breadcrumb, Flex, Typography } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export function PageHeader({ title, subtitle, extra, breadcrumb }: {
  title: ReactNode
  subtitle?: ReactNode
  extra?: ReactNode
  breadcrumb?: { label: string; to?: string }[]
}) {
  return (
    <header style={{ marginBottom: 16 }}>
      {breadcrumb && (
        <Breadcrumb style={{ marginBottom: 8 }}
                    items={breadcrumb.map((item) => ({ title: item.to ? <Link to={item.to}>{item.label}</Link> : item.label }))} />
      )}
      <Flex justify="space-between" align="start" gap={16} wrap>
        <div>
          <Typography.Title level={2} style={{ margin: 0 }}>{title}</Typography.Title>
          {subtitle && <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0' }}>{subtitle}</Typography.Paragraph>}
        </div>
        {extra && <Flex gap={8} wrap>{extra}</Flex>}
      </Flex>
    </header>
  )
}
