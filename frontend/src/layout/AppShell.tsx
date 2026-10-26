import { DownOutlined, LogoutOutlined, MenuOutlined } from '@ant-design/icons'
import { App as AntApp, Button, Drawer, Dropdown, Grid, Layout, Menu } from 'antd'
import { Suspense, useEffect, useMemo, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/auth/AuthProvider'
import { ROLE_LABELS } from '@/auth/types'
import { Brand } from '@/components/Logo'
import { LoadingState } from '@/components/states'
import { PortalFooter, PortalIdentity } from '@/components/PortalChrome'
import { appRoutes, BellSlot, HeaderSearchSlot } from '@/routes/registry'
import { GROUPS, navItemsFor, selectedPath } from './navigation'

const { Content } = Layout

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

  const categories = GROUPS.map((group) => ({
    key: group,
    label: <span>{group} <DownOutlined aria-hidden className="category-chevron" /></span>,
    children: items.filter((item) => item.group === group).map((item) => ({
      key: item.path, icon: item.icon, label: <Link to={item.path}>{item.label}</Link>,
    })),
  })).filter((group) => group.children.length > 0)
  const menuItems = [{ key: '/', label: <Link to="/">Home</Link> }, ...categories]
  const selection = location.pathname === '/' ? ['/'] : selectedPath(items, location.pathname)

  return (
    <div className="portal-frame">
      <a className="skip-link" href="#main">Skip to main content</a>
      <header className="portal-masthead">
        <PortalIdentity />
        <div className="masthead-actions">
          {/* Keep search and notifications beside the account, without another toolbar. */}
          {HeaderSearchSlot && items.some((item) => item.path === '/records') &&
            <div className="header-search"><HeaderSearchSlot /></div>}
          {BellSlot && <BellSlot />}
          <Dropdown trigger={['click']} placement="bottomRight" menu={{ items: [
            { key: 'who', disabled: true, label: user?.institution?.name ?? 'Pramaan workspace' },
            { type: 'divider' },
            { key: 'logout', icon: <LogoutOutlined />, label: 'Sign out', onClick: () => void signOut() },
          ] }}>
            <Button type="text" className="account-button" aria-label="Account menu">
              <span className="avatar" aria-hidden>{initials(user?.display_name ?? '')}</span>
              <span className="account-text"><span>{user?.display_name}</span>
                {user?.role && <small>{ROLE_LABELS[user.role]}</small>}</span>
              <DownOutlined aria-hidden />
            </Button>
          </Dropdown>
        </div>
      </header>
      <nav className="category-navigation" aria-label="Main">
        {desktop ? <Menu theme="dark" mode="horizontal" className="category-menu"
          selectedKeys={selection} items={menuItems} triggerSubMenuAction="click" /> :
          <Button className="menu-toggle" type="text" aria-label="Open navigation" icon={<MenuOutlined />}
            onClick={() => setDrawerOpen(true)}>Select section <DownOutlined aria-hidden /></Button>}
      </nav>
      {!desktop && (
        <Drawer placement="left" width={288} open={drawerOpen} onClose={() => setDrawerOpen(false)} closable
                title={<Brand compact size={30} />} styles={{ body: { padding: 0, background: '#fff' }, header: { background: '#fff' } }}>
          <nav className="mobile-category-nav" aria-label="Sections">
            <Menu theme="light" mode="inline" selectedKeys={selection} items={menuItems}
              defaultOpenKeys={items.filter(item => selection.includes(item.path)).map(item => item.group)} />
          </nav>
        </Drawer>
      )}
      <Layout className="app-shell">
        <Content id="main" tabIndex={-1} className="shell-content">
          <Suspense fallback={<LoadingState />}>
            <Outlet />
          </Suspense>
        </Content>
        <PortalFooter />
      </Layout>
    </div>
  )
}
