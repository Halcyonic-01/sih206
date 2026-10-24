import type { UseQueryResult } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { EmptyState, LoadingState, QueryError } from './states'

/**
 * Standard loading / error / empty handling around a query.
 * `isEmpty` decides when to show the empty state instead of children.
 */
export function QueryBoundary<T>({ query, isEmpty, empty, children }: {
  query: UseQueryResult<T>
  isEmpty?: (data: T) => boolean
  empty?: ReactNode
  children: (data: T) => ReactNode
}) {
  if (query.isPending) return <LoadingState />
  if (query.isError) return <QueryError error={query.error} onRetry={() => void query.refetch()} />
  if (isEmpty?.(query.data)) return <>{empty ?? <EmptyState />}</>
  return <>{children(query.data)}</>
}
