import { DownOutlined, LogoutOutlined, MenuOutlined } from '@ant-design/icons'
import { App as AntApp, Button, Drawer, Dropdown, Grid, Layout, Menu } from 'antd'
import { Suspense, useEffect, useMemo, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/AuthProvider'
import { ROLE_LABELS } from '@/auth/types'
import { Brand } from '@/components/Logo'
import { LoadingState } from '@/components/states'
import { appRoutes, BellSlot, HeaderSearchSlot } from '@/routes/registry'
import { GROUPS, navItemsFor, selectedPath } from './navigation'

const { Header, Sider, Content, Footer } = Layout

function initials(name: string) {
  const letters = name.trim().split(/\s+/).map((part) => part[0]).filter(Boolean)
  return (letters[0] ?? '?').concat(letters.length > 1 ? letters[letters.length - 1]! : '').toUpperCase()
}

export function AppShell() {
  const { user, logout } = useAuth()
  const { message } = AntApp.useApp()
  const location = useLocation()
  const navigate = useNavigate()
  const screens = Grid.useBreakpoint()
  const desktop = screens.lg === true
  const [drawerOpen, setDrawerOpen] = useState(false)
  const items = useMemo(() => navItemsFor(appRoutes, user?.role ?? null), [user?.role])

  // Moving to another page closes the phone navigation; a wider window never leaves it open.
  useEffect(() => setDrawerOpen(false), [location.pathname])
  useEffect(() => { if (desktop) setDrawerOpen(false) }, [desktop])

  async function signOut() {
    try {
      await logout()
    } catch {
      message.warning('Signed out on this device. The server could not be reached.')
    }
    navigate('/login', { replace: true })
  }

  const menu = (
    <Menu theme="dark" mode="inline" selectedKeys={selectedPath(items, location.pathname)}
          items={GROUPS.map((group) => ({
            type: 'group' as const, key: group, label: group,
            children: items.filter((item) => item.group === group).map((item) => ({
              key: item.path, icon: item.icon, label: <Link to={item.path}>{item.label}</Link>,
            })),
          })).filter((group) => group.children.length > 0)} />
  )
  const account = (
    <div className="sider-user">
      <strong>{user?.display_name}</strong>
      {user?.institution?.name ?? (user?.unit ? `${user.unit} unit` : 'AICTE')}
    </div>
  )

  return (
    <Layout className="app-shell" hasSider>
      <a className="skip-link" href="#main">Skip to main content</a>
      {desktop && (
        <Sider className="app-sider" width={264} theme="dark" aria-label="Primary navigation">
          <div className="sider-brand"><Link to="/" aria-label="Pramaan home"><Brand inverse /></Link></div>
          <nav className="sider-nav" aria-label="Main">{menu}</nav>
          {account}
        </Sider>
      )}
      {!desktop && (
        <Drawer placement="left" width={288} open={drawerOpen} onClose={() => setDrawerOpen(false)} closable
                title={<Brand compact size={30} />} styles={{ body: { padding: 0, background: '#0f2447' }, header: { background: '#fff' } }}>
          <nav className="sider-nav" aria-label="Main">{menu}</nav>
          {account}
        </Drawer>
      )}
      <Layout>
        <Header className="shell-header">
          <Button className="menu-toggle" type="text" size="large" aria-label="Open navigation" icon={<MenuOutlined />}
                  onClick={() => setDrawerOpen(true)} />
          <Link to="/" className="header-brand" aria-label="Pramaan home"><Brand compact size={30} /></Link>
          {/* Search opens the records list, so it is offered only to accounts that can open it. */}
          <div className="header-search">{HeaderSearchSlot && items.some((item) => item.path === '/records') && <HeaderSearchSlot />}</div>
          <div className="header-actions">
            {BellSlot && <BellSlot />}
            <Dropdown trigger={['click']} placement="bottomRight" menu={{
              items: [
                { key: 'who', disabled: true, label: <span>{user?.institution?.name ?? (user?.unit ? `${user.unit} unit` : 'AICTE')}</span> },
                { type: 'divider' },
                { key: 'logout', icon: <LogoutOutlined />, label: 'Sign out', onClick: () => void signOut() },
              ],
            }}>
              <Button type="text" className="account-button" aria-label="Account menu">
                <span className="avatar" aria-hidden>{initials(user?.display_name ?? '')}</span>
                <span className="account-text">
                  <span>{user?.display_name}</span>
                  {user?.role && <small>{ROLE_LABELS[user.role]}</small>}
                </span>
                <DownOutlined aria-hidden />
              </Button>
            </Dropdown>
          </div>
        </Header>
        <Content id="main" tabIndex={-1} className="shell-content">
          <Suspense fallback={<LoadingState />}>
            <Outlet />
          </Suspense>
        </Content>
        <Footer className="shell-footer">
          <p>© All India Council for Technical Education · Pramaan Security Deposit Portal</p>
          <p>“Accepted” means accepted for tracking. It is not verification by the bank.</p>
        </Footer>
      </Layout>
    </Layout>
  )
}
