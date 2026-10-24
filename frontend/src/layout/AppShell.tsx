import { DownOutlined, LogoutOutlined, MenuOutlined, UserOutlined } from '@ant-design/icons'
import { App as AntApp, Button, Dropdown, Flex, Layout, Menu, Tag, Typography } from 'antd'
import { Suspense, useMemo, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/AuthProvider'
import { ROLE_LABELS } from '@/auth/types'
import { LoadingState } from '@/components/states'
import { appRoutes, BellSlot, HeaderSearchSlot } from '@/routes/registry'
import type { AppRoute } from '@/routes/types'

const { Header, Sider, Content, Footer } = Layout

function menuFor(role: string | null): AppRoute[] {
  return appRoutes
    .filter((route) => route.menu && (!route.roles || (role && route.roles.includes(role as never))))
    .sort((a, b) => (a.menu?.order ?? 100) - (b.menu?.order ?? 100))
}

/** Longest matching menu path wins, so /records/12 highlights "Records". */
function selectedKey(entries: AppRoute[], pathname: string) {
  const match = entries
    .filter((entry) => pathname === entry.path || pathname.startsWith(entry.path.replace(/\/$/, '') + '/') || entry.path === '/' && pathname === '/')
    .sort((a, b) => b.path.length - a.path.length)[0]
  return match ? [match.path] : []
}

export function AppShell() {
  const { user, logout } = useAuth()
  const { message } = AntApp.useApp()
  const location = useLocation()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const entries = useMemo(() => menuFor(user?.role ?? null), [user?.role])

  async function signOut() {
    try {
      await logout()
    } catch {
      message.warning('Signed out locally. The server could not be reached.')
    }
    navigate('/login', { replace: true })
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <a className="skip-link" href="#main">Skip to main content</a>
      <Sider breakpoint="lg" collapsedWidth={0} collapsed={collapsed} onCollapse={setCollapsed}
             width={232} theme="dark" aria-label="Primary navigation">
        <div className="brand">
          <Link to="/"><strong>AICTE</strong> Security Deposit</Link>
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={selectedKey(entries, location.pathname)}
              items={entries.map((entry) => ({
                key: entry.path, icon: entry.menu?.icon,
                label: <Link to={entry.path}>{entry.menu?.label}</Link>,
              }))} />
      </Sider>
      <Layout>
        <Header className="shell-header">
          <Button type="text" aria-label="Toggle navigation" icon={<MenuOutlined />}
                  onClick={() => setCollapsed((value) => !value)} className="menu-toggle" />
          <div className="header-search">{HeaderSearchSlot && <HeaderSearchSlot />}</div>
          <Flex align="center" gap={12}>
            {BellSlot && <BellSlot />}
            <Dropdown trigger={['click']} menu={{
              items: [
                { key: 'who', disabled: true, label: <span>{user?.institution?.name ?? 'AICTE'}</span> },
                { type: 'divider' },
                { key: 'logout', icon: <LogoutOutlined />, label: 'Sign out', onClick: () => void signOut() },
              ],
            }}>
              <Button type="text" icon={<UserOutlined />} aria-label="Account menu">
                <span className="user-name">{user?.display_name}</span>
                {user?.role && <Tag color="blue" style={{ marginInlineStart: 8, marginInlineEnd: 0 }}>{ROLE_LABELS[user.role]}</Tag>}
                <DownOutlined />
              </Button>
            </Dropdown>
          </Flex>
        </Header>
        <Content id="main" tabIndex={-1} className="shell-content">
          <Suspense fallback={<LoadingState />}>
            <Outlet />
          </Suspense>
        </Content>
        <Footer className="shell-footer">
          <Typography.Text type="secondary">
            Prototype for SIH 2026 problem statement 26265 · synthetic data only · "Accepted" means accepted for tracking,
            not verified by the bank.
          </Typography.Text>
        </Footer>
      </Layout>
    </Layout>
  )
}
