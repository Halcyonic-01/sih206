import { localizedLabels } from '@/i18n';
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
  /** Two-factor sign-in state. Absent on responses that do not carry it. */
  mfa?: MfaStatus
}

export interface MfaStatus {
  /** A staff role that can use an authenticator app. */
  in_scope: boolean
  enrolled: boolean
  /** Enrolment is compulsory for this account (MFA_REQUIRED). */
  required: boolean
  verified_recently: boolean
}

/** The password step succeeded but a code from the authenticator app is still needed. */
export interface MfaChallenge { mfa_required: true }

export const ROLE_LABELS: Record<Role, string> = localizedLabels({
  institution: 'Institution',
  officer: 'Dealing officer',
  authority: 'Authority',
  clearance: 'Clearance unit',
  auditor: 'Auditor',
})
