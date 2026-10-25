import type { ReactNode } from 'react'
import { Link, useInRouterContext } from 'react-router-dom'

/** The single page title block: breadcrumb, h1, one-line description and the page's primary actions. */
export function PageHeader({ title, subtitle, extra, breadcrumb }: {
  title: ReactNode
  subtitle?: ReactNode
  extra?: ReactNode
  breadcrumb?: { label: string; to?: string }[]
}) {
  // Feature components can render without a router (they take navigation as props); then crumbs are plain text.
  const routed = useInRouterContext()
  return (
    <header className="page-header">
      {breadcrumb && (
        <nav aria-label="Breadcrumb" className="breadcrumb">
          <ol>
            {breadcrumb.map((item, index) => (
              <li key={item.label}>{item.to && routed ? <Link to={item.to}>{item.label}</Link>
                : <span aria-current={index === breadcrumb.length - 1 ? 'page' : undefined}>{item.label}</span>}</li>
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
