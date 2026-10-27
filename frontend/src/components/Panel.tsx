import { t as tr, useLanguage } from '@/i18n';
import type { ReactNode } from 'react'

/** A titled white card for plain HTML content. Use antd Card where a component already brings its own layout. */
export function Panel({ title, extra, children, flush = false, id, className = '' }: {
  title?: ReactNode
  extra?: ReactNode
  children: ReactNode
  flush?: boolean
  id?: string
  className?: string
}) {
  useLanguage();
  const heading = id ? `${id}-title` : undefined
  return (
    <section className={`panel${flush ? ' panel--flush' : ''} ${className}`.trim()} aria-labelledby={title ? heading : undefined}>
      {(title || extra) && (
        <div className="panel__head">
          {title && <h2 className="panel__title" id={heading}>{title}</h2>}
          {extra && <div className="panel__extra">{extra}</div>}
        </div>
      )}
      <div className="panel__body">{children}</div>
    </section>
  )
}

/** Large number with a label: the building block of dashboards and KPI pages. */
export function StatCard({ label, value, hint, tone = 'neutral', onClick }: {
  label: string
  value: ReactNode
  hint?: ReactNode
  tone?: 'neutral' | 'info' | 'success' | 'warning' | 'danger'
  onClick?: () => void
}) {
  useLanguage();
  const body = (
    <>
      <span className="stat__label">{label}</span>
      <span className="stat__value">{value}</span>
      {hint && <span className="stat__hint">{hint}</span>}
    </>
  )
  return onClick
    ? <button type="button" className={`stat stat--${tone} stat--action`} onClick={onClick}>{body}</button>
    : <div className={`stat stat--${tone}`}>{body}</div>
}

/** Label/value pairs (GOV.UK "summary list"): one column on phones, label beside value from tablet up. */
export function SummaryList({ items }: { items: { label: string; value: ReactNode }[] }) {
  useLanguage();
  return (
    <dl className="summary-list">
      {items.map((item) => (
        <div className="summary-list__row" key={item.label}>
          <dt>{tr(item.label)}</dt>
          <dd>{item.value === null || item.value === undefined || item.value === '' ? '—' : item.value}</dd>
        </div>
      ))}
    </dl>
  )
}

/** Filters laid out as a responsive grid with the actions at the end. */
export function FilterBar({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  useLanguage();
  return (
    <div className="filter-bar">
      <div className="filter-bar__fields">{children}</div>
      {actions && <div className="filter-bar__actions">{actions}</div>}
    </div>
  )
}
