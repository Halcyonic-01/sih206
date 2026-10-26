import { t as tr, useLanguage } from '@/i18n';
import { Alert, Button, Empty, Skeleton } from 'antd'
import type { ReactNode } from 'react'
import { ApiError } from '@/api/client'
import { errorMessage } from '@/api/forms'
import { LogoMark } from './Logo'

export function LoadingState({ rows = 4 }: { rows?: number }) {
  useLanguage();
  return <div role="status" aria-live="polite" aria-label={tr("Loading")}><Skeleton active paragraph={{ rows }} /></div>
}

export function EmptyState({ title = 'Nothing to show yet', detail, action }:
  { title?: string; detail?: ReactNode; action?: ReactNode }) {
  useLanguage();
  return (
    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={<><strong>{tr(title)}</strong>{detail && <div>{typeof detail === 'string' ? tr(detail) : detail}</div>}</>}>
      {action}
    </Empty>
  )
}

export function ErrorState({ status, title, detail, onRetry }:
  { status?: 403 | 404 | 409 | 500; title: string; detail?: ReactNode; onRetry?: () => void }) {
  useLanguage();
  return (
    <div className="state-page">
      <LogoMark size={52} />
      {status && <span className="state-code">{status}</span>}
      <h2 className="state-title">{tr(title)}</h2>
      {detail && <div className="state-detail">{detail}</div>}
      {onRetry && <Button onClick={onRetry}>{tr("Try again")}</Button>}
    </div>
  )
}

/** Renders the right state for a failed request: 403, 404, 409 ("record changed, reload") or a generic error. */
export function QueryError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  useLanguage();
  if (error instanceof ApiError) {
    if (error.isForbidden) {
      return <ErrorState status={403} title={tr("Not allowed")} detail={error.message} />
    }
    if (error.isNotFound) {
      return <ErrorState status={404} title={tr("Not found")} detail={tr("It may not exist, or it belongs to another institution.")} />
    }
    if (error.isConflict) return <ConflictBanner error={error} onReload={onRetry} />
  }
  return <ErrorState title={tr("Something went wrong")} detail={errorMessage(error)} onRetry={onRetry} />
}

/** Shown when a write loses the optimistic-lock race (HTTP 409). */
export function ConflictBanner({ error, onReload }: { error: unknown; onReload?: () => void }) {
  useLanguage();
  return (
    <Alert type="warning" showIcon
           message={tr("This record changed")}
           description={<>{errorMessage(error)} {tr("  Reload to see the latest version, then repeat your change.")}</>}
           action={onReload && <Button size="small" onClick={onReload}>{tr("Reload")}</Button>} />
  )
}
