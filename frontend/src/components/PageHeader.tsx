import { t as tr, useLanguage } from '@/i18n';
import type { ReactNode } from 'react'
import { Link, useInRouterContext } from 'react-router-dom'

/** The single page title block: breadcrumb, h1, one-line description and the page's primary actions. */
export function PageHeader({ title, subtitle, extra, breadcrumb }: {
  title: ReactNode
  subtitle?: ReactNode
  extra?: ReactNode
  breadcrumb?: { label: string; to?: string }[]
}) {
  useLanguage();
  // Feature components can render without a router (they take navigation as props); then crumbs are plain text.
  const routed = useInRouterContext()
  const crumbs = breadcrumb ?? (routed && typeof title === 'string'
    ? [{ label: tr("Home"), to: '/' }, { label: title }] : undefined)
  return (
    <header className="page-header">
      {crumbs && (
        <nav aria-label={tr("Breadcrumb")} className="breadcrumb">
          <ol>
            {crumbs.map((item, index) => (
              <li key={item.label}>{item.to && routed ? <Link to={item.to}>{item.label}</Link>
                : <span aria-current={index === crumbs.length - 1 ? 'page' : undefined}>{item.label}</span>}</li>
            ))}
          </ol>
        </nav>
      )}
      <div className="page-header__row">
        <div className="page-header__text">
          <h1 className="page-title">{title}</h1>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
        </div>
        {extra && <div className="page-actions">{extra}</div>}
      </div>
    </header>
  )
}
