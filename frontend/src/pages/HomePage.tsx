import { Card, List, Typography } from 'antd'
import { Link } from 'react-router-dom'
import { useAuth } from '@/auth/AuthProvider'
import { ROLE_LABELS } from '@/auth/types'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState } from '@/components/states'
import { appRoutes } from '@/routes/registry'

/** Fallback landing page, used until a feature registers its own route for "/". */
export default function HomePage() {
  const { user } = useAuth()
  const links = appRoutes.filter((route) => route.menu && (!route.roles || (user?.role && route.roles.includes(user.role))))
  return (
    <>
      <PageHeader title={`Welcome, ${user?.display_name ?? ''}`}
                  subtitle={user?.role ? `Signed in as ${ROLE_LABELS[user.role]}` : undefined} />
      <Card>
        {links.length === 0 ? (
          <EmptyState title="No screens are available for your role yet"
                      detail="Use the previous interface under /legacy/ until your screens are published." />
        ) : (
          <List header={<Typography.Text strong>Where to start</Typography.Text>} dataSource={links}
                renderItem={(route) => <List.Item><Link to={route.path}>{route.menu?.label}</Link></List.Item>} />
        )}
        <Typography.Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 0 }}>
          The previous interface remains available at <a href="/legacy/">/legacy/</a> until 28 Oct 2026.
        </Typography.Paragraph>
      </Card>
    </>
  )
}
