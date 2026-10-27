/** Human wording and colour tone for the codes the API returns. Unknown codes fall back to a readable form. */
import { t, localizedLabels } from '@/i18n';
export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

export interface Labelled { label: string; tone: Tone }

const titleCase = (code: string) => code.toLowerCase().replaceAll('_', ' ').replace(/^./, (c) => c.toUpperCase())

function lookup(table: Record<string, Labelled>, code: string | null | undefined): Labelled {
  if (!code) return { label: '—', tone: 'neutral' }
  const value = table[code] ?? { label: titleCase(code), tone: 'neutral' as const };
  return {...value, label: t(code === 'OPEN' ? 'Open status' : value.label)};
}

const STATUS: Record<string, Labelled> = {
  DRAFT: { label: 'Draft', tone: 'neutral' },
  SUBMITTED: { label: 'Submitted', tone: 'info' },
  CHANGES_REQUESTED: { label: 'Changes requested', tone: 'warning' },
  ACCEPTED: { label: 'Accepted', tone: 'success' },
  PENDING: { label: 'Pending', tone: 'info' },
  APPROVED: { label: 'Approved', tone: 'success' },
  REJECTED: { label: 'Rejected', tone: 'danger' },
  COMPLETED: { label: 'Completed', tone: 'success' },
  OPEN: { label: 'Open', tone: 'info' },
  CLEARED: { label: 'Cleared', tone: 'success' },
  OBJECTION: { label: 'Objection', tone: 'danger' },
  HOLD: { label: 'On hold', tone: 'warning' },
  PROPOSED: { label: 'Proposed', tone: 'info' },
  CONFIRMED: { label: 'Confirmed', tone: 'success' },
  WAIVED: { label: 'Waived', tone: 'neutral' },
  ISSUED: { label: 'Issued', tone: 'success' },
  REVOKED: { label: 'Revoked', tone: 'danger' },
  SENT: { label: 'Sent', tone: 'success' },
  FAILED: { label: 'Failed', tone: 'danger' },
  EXPIRED: { label: 'Expired', tone: 'neutral' },
  LOCKED: { label: 'Locked', tone: 'danger' },
  UNKNOWN: { label: 'Not established', tone: 'neutral' },
  DUE: { label: 'Due', tone: 'warning' },
  PARTIALLY_MET: { label: 'Partly met', tone: 'warning' },
  MET: { label: 'Met', tone: 'success' },
  EXEMPT: { label: 'Exempt', tone: 'neutral' },
  ACTIVE: { label: 'Active', tone: 'success' },
  SIMULATED_MATCH: { label: 'Match', tone: 'success' },
  DISCREPANCY: { label: 'Discrepancy', tone: 'danger' },
  AMBIGUOUS: { label: 'Ambiguous', tone: 'warning' },
  UNMATCHED: { label: 'No match', tone: 'neutral' },
}
export const statusLabel = (code: string | null | undefined) => lookup(STATUS, code)

const VERIFICATION: Record<string, Labelled> = {
  DECLARED: { label: 'Declared', tone: 'neutral' },
  REVIEWED: { label: 'Document reviewed', tone: 'info' },
  CONFIRMED: { label: 'Confirmed', tone: 'success' },
  DISCREPANCY: { label: 'Discrepancy', tone: 'danger' },
}
export const verificationLabel = (code: string | null | undefined) => lookup(VERIFICATION, code)

export const MODE_LABELS: Record<string, string> = { FDR: 'FDR', RTGS: 'RTGS', RPGF: 'RPGF' }

export const CATEGORY_LABELS: Record<string, string> = localizedLabels({
  all: 'All records', active: 'Active', expiring: 'Expiring', matured: 'Matured', renewed: 'Renewed',
  released: 'Released', pending: 'Pending',
})

export const CATEGORY_HINTS: Record<string, string> = localizedLabels({
  active: 'Accepted and not renewed or released. Includes matured records awaiting action.',
  expiring: 'Maturing within the reminder window.',
  matured: 'Maturity date reached, with no successor accepted.',
  renewed: 'Replaced by an accepted renewal.',
  released: 'Release completed.',
  pending: 'Submitted or waiting for corrections.',
})

const INTERVENTION: Record<string, string> = {
  maturity_follow_up: 'Matured: assess renewal or release',
  blocking_observation: 'Blocking observation unresolved',
  ageing_correction: 'Corrections overdue',
  discrepancy: 'Verification discrepancy',
}
export const interventionLabel = (code: string) => t(INTERVENTION[code] ?? titleCase(code))

const FINDINGS: Record<string, string> = {
  ISSUER_UNKNOWN: 'Issuing bank not recognised',
  ISSUER_UNCONFIRMED: 'Issuing bank not independently confirmed',
  CROSS_INSTITUTION_POSSIBLE_DUPLICATE: 'Possible duplicate of another institution’s record',
  POSSIBLE_DUPLICATE: 'Possible duplicate record',
  NEAR_DUPLICATE_SCAN: 'First page looks like another document',
  ISSUER_MERGED: 'Issuing bank merged into another bank',
  ISSUER_NAME_MISMATCH: 'Bank name differs from the IFSC listing',
  ISSUER_BRANCH_MISMATCH: 'Branch differs from the IFSC listing',
  IFSC_NOT_IN_DIRECTORY: 'IFSC not in the loaded directory',
  AMOUNT_WORDS_MISMATCH: 'Amount in words differs from the figures',
  HOLDER_NOT_AICTE: 'Holder names do not include AICTE',
  LIEN_NOT_MARKED: 'No lien marked in favour of AICTE',
  MISSING_FDR_DOCUMENT: 'Supporting document missing',
  AMOUNT_SHORTFALL: 'Deposit below the required amount',
  TERM_GAP: 'Coverage ends before the obligation term',
  PROOF_OVERDUE: 'Deposit proof overdue',
}
export const findingLabel = (code: string) => t(FINDINGS[code] ?? titleCase(code))

export const RELEASE_PATH_LABELS: Record<string, string> = localizedLabels({
  TERM_COMPLETE: 'Term complete',
  PROGRESSIVE_CLOSURE: 'Progressive closure',
  MERGER: 'Merger',
  CONVERSION_TO_UNIVERSITY: 'Conversion to university',
  CLOSURE_BY_AICTE: 'Closure by AICTE',
})

/** "DRAFT_CREATED" -> "Draft created". Used where the API sends a code and no label exists. */
export const humanize = (code: string) => t(titleCase(code))
