import { t as tr, useLanguage } from '@/i18n';
import { Link } from 'react-router-dom'
import { useAuth } from '@/auth/AuthProvider'
import { ROLE_LABELS } from '@/auth/types'
import { PageHeader } from '@/components/PageHeader'
import { EmptyState } from '@/components/states'
import { navItemsFor } from '@/layout/navigation'
import { appRoutes } from '@/routes/registry'

/** Start page: the screens this account can open, each with one line on what it is for. */
export default function HomePage() {
  useLanguage();
  const { user } = useAuth()
  const items = navItemsFor(appRoutes, user?.role ?? null)
  const first = user?.display_name?.split(' ')[0] || user?.username || ''
  return (
    <>
      <section className="workspace-intro">
        <PageHeader title={tr('Welcome, {name}', {name: first})}
                  subtitle={[user?.role ? ROLE_LABELS[user.role] : null, user?.institution?.name].filter(Boolean).join(' · ')} />
      </section>
      {items.length === 0 ? (
        <EmptyState title={tr("No screens are available for your account")} detail={tr("Ask the portal administrator to assign a role.")} />
      ) : (
        <div className="action-grid">
          {items.map((item) => (
            <Link key={item.path} to={item.path} className="action-card">
              <span className="action-card__icon" aria-hidden>{item.icon}</span>
              <span className="action-card__title">{tr(item.label)}</span>
              {item.description && <span className="action-card__text">{tr(item.description)}</span>}
            </Link>
          ))}
        </div>
      )}
    </>
  )
}
