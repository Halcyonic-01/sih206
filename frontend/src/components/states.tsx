import { Alert, Button, Empty, Skeleton } from 'antd'
import type { ReactNode } from 'react'
import { ApiError } from '@/api/client'
import { errorMessage } from '@/api/forms'
import { LogoMark } from './Logo'

export function LoadingState({ rows = 4 }: { rows?: number }) {
  return <div role="status" aria-live="polite" aria-label="Loading"><Skeleton active paragraph={{ rows }} /></div>
}

export function EmptyState({ title = 'Nothing to show yet', detail, action }:
  { title?: string; detail?: ReactNode; action?: ReactNode }) {
  return (
    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={<><strong>{title}</strong>{detail && <div>{detail}</div>}</>}>
      {action}
    </Empty>
  )
}

export function ErrorState({ status, title, detail, onRetry }:
  { status?: 403 | 404 | 409 | 500; title: string; detail?: ReactNode; onRetry?: () => void }) {
  return (
    <div className="state-page">
      <LogoMark size={52} />
      {status && <span className="state-code">{status}</span>}
      <h2 className="state-title">{title}</h2>
      {detail && <div className="state-detail">{detail}</div>}
      {onRetry && <Button onClick={onRetry}>Try again</Button>}
    </div>
  )
}

/** Renders the right state for a failed request: 403, 404, 409 ("record changed, reload") or a generic error. */
export function QueryError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (error instanceof ApiError) {
    if (error.isForbidden) {
      return <ErrorState status={403} title="Not allowed" detail={error.message} />
    }
    if (error.isNotFound) {
      return <ErrorState status={404} title="Not found" detail="It may not exist, or it belongs to another institution." />
    }
    if (error.isConflict) return <ConflictBanner error={error} onReload={onRetry} />
  }
  return <ErrorState title="Something went wrong" detail={errorMessage(error)} onRetry={onRetry} />
}

/** Shown when a write loses the optimistic-lock race (HTTP 409). */
export function ConflictBanner({ error, onReload }: { error: unknown; onReload?: () => void }) {
  return (
    <Alert type="warning" showIcon
           message="This record changed"
           description={<>{errorMessage(error)} Reload to see the latest version, then repeat your change.</>}
           action={onReload && <Button size="small" onClick={onReload}>Reload</Button>} />
  )
}
