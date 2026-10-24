import type { Role } from '@/api/client'

export interface CurrentUser {
  id: number
  username: string
  display_name: string
  /** null when the account exists but has no portal role. */
  role: Role | null
  institution: { id: number; code: string; name: string } | null
  /** PGRC, VIGILANCE or GRANTS for a clearance-unit account, otherwise null. */
  unit: 'PGRC' | 'VIGILANCE' | 'GRANTS' | null
}

export const ROLE_LABELS: Record<Role, string> = {
  institution: 'Institution',
  officer: 'Dealing officer',
  authority: 'Authority',
  clearance: 'Clearance unit',
  auditor: 'Auditor',
}
