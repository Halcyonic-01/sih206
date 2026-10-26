import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { get, post, type Page } from '@/api/client'

export interface AppNotification {
  id: number
  template_id: string
  subject: string
  body: string
  link: string
  severity: 'info' | 'warning' | 'critical'
  created_at: string
  read_at: string | null
  is_read: boolean
  translations?: {hi?: {subject: string; body: string}}
}

const KEY = ['notifications'] as const

/** Only in-app paths are followed; anything else (absolute URLs, //host) is ignored. */
export function safeLink(link: string): string | null {
  return link.startsWith('/') && !link.startsWith('//') ? link : null
}

export function useUnreadCount() {
  return useQuery({
    queryKey: [...KEY, 'unread-count'],
    queryFn: () => get<{ count: number }>('/notifications/unread-count/'),
    refetchInterval: 30_000,
    select: (data) => data.count,
  })
}

export function useNotifications(params: { unread?: boolean; page?: number; pageSize?: number }, enabled = true) {
  return useQuery({
    queryKey: [...KEY, 'list', params],
    queryFn: () => get<Page<AppNotification>>('/notifications/', {
      unread: params.unread ? 1 : undefined, page: params.page, page_size: params.pageSize,
    }),
    enabled,
  })
}

function useInvalidate() {
  const client = useQueryClient()
  return () => client.invalidateQueries({ queryKey: KEY })
}

export function useMarkRead() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (id: number) => post(`/notifications/${id}/read/`),
    onSuccess: invalidate,
  })
}

export function useMarkAllRead() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: () => post<{ marked: number }>('/notifications/read-all/'),
    onSuccess: invalidate,
  })
}
