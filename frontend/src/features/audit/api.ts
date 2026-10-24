import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { get, type Page, type QueryValue } from '@/api/client'

export interface AuditEventRow {
  id: number
  created_at: string
  action: string
  reason: string
  instrument: { id: number; reference: string; institution: string }
  actor: { id: number; username: string }
}

export interface AuditEventDetail extends AuditEventRow {
  before: Record<string, unknown>
  after: Record<string, unknown>
  changes: { field: string; before: unknown; after: unknown }[]
}

export interface AccessLogRow {
  id: number
  created_at: string
  username: string
  user: number | null
  action: string
  object_type: string
  object_id: number | null
  detail: string
  path: string
  ip_address: string | null
  user_agent: string
  request_id: string
}

export interface AuditFacets {
  actions: string[]
  actors: { id: number; username: string }[]
  institutions: string[]
}

export interface AccessFacets {
  actions: string[]
  object_types: string[]
}

export type Filters = Record<string, QueryValue>

export function useAuditEvents(filters: Filters, page: number) {
  return useQuery({
    queryKey: ['audit', 'events', filters, page],
    queryFn: () => get<Page<AuditEventRow>>('/audit/events/', { ...filters, page, page_size: 25 }),
    placeholderData: keepPreviousData,
  })
}

export function useAuditEvent(id: number | null) {
  return useQuery({
    queryKey: ['audit', 'event', id],
    queryFn: () => get<AuditEventDetail>(`/audit/events/${id}/`),
    enabled: id !== null,
  })
}

export function useAuditFacets() {
  return useQuery({ queryKey: ['audit', 'facets'], queryFn: () => get<AuditFacets>('/audit/events/facets/'), staleTime: 60_000 })
}

export function useAccessLog(filters: Filters, page: number) {
  return useQuery({
    queryKey: ['audit', 'access', filters, page],
    queryFn: () => get<Page<AccessLogRow>>('/audit/access-log/', { ...filters, page, page_size: 25 }),
    placeholderData: keepPreviousData,
  })
}

export function useAccessFacets() {
  return useQuery({ queryKey: ['audit', 'access-facets'], queryFn: () => get<AccessFacets>('/audit/access-log/facets/'), staleTime: 60_000 })
}
