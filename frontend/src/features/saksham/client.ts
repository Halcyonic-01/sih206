// Provisional owned interface. K2 injects its shared client; no fetch/auth/router here.
export interface Transport {
  get<T>(path: string, signal?: AbortSignal): Promise<T>;
  post<T>(path: string, body: unknown | FormData): Promise<T>;
  download(path: string): Promise<void>;
}
export interface Failure { status?: number; message?: string }
export const api = (path: string) => `/api/${path}`;
export function errorMessage(error: unknown): string {
  const status = (error as Failure | null)?.status;
  if (status === 409) return 'Record changed. Reload, review the updated values and try again.';
  if (status === 401) return 'Session expired. Sign in again; no action was replayed.';
  if (status === 403 || status === 404) return 'This record or action is unavailable.';
  if (status === 400) return 'Check the required fields and supplied evidence.';
  return 'Service unavailable. Refresh saved state before retrying an action.';
}
export function money(value: number | string | null | undefined): string {
  if (value == null) return 'Unavailable';
  if (typeof value !== 'number' && typeof value !== 'string') return 'Unavailable';
  if (typeof value === 'number' && (!Number.isSafeInteger(value) || value < 0)) return 'Unavailable';
  if (typeof value === 'string' && (!/^\d+$/.test(value) || value.length > 19)) return 'Unavailable';
  const exact = BigInt(value);
  return `INR ${(exact / 100n).toLocaleString('en-IN')}.${String(exact % 100n).padStart(2, '0')}`;
}
export function paise(text: string): number {
  if (!/^\d+(\.\d{1,2})?$/.test(text)) throw new Error('Use a positive INR amount with at most two decimals.');
  const [whole, fraction = ''] = text.split('.');
  const amount = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  if (amount <= 0n || amount > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error('Amount is outside the supported range.');
  return Number(amount);
}

export interface Page<T> { count?: number; results: T[] }
export type Paise = number | string;
export interface Institution { id: number; name: string; code: string; version: number | null; profile: null | {
  aicte_id: string; trust_name: string; region: string; state: string; institution_type: string;
} }
export interface Approval { id: number; programme: string; level: string; approved_on: string; loa_ref: string }
export interface Obligation { id: number; required_paise: Paise | null; term_start: string | null;
  term_end: string | null; basis: string; status: string; version: number }
export interface Assessment { outcome: string; reason_codes?: string[]; findings?: {
  code: string; field: string; source_clause: string; as_of: string }[] }
export interface ObligationDetail extends Obligation { assessment: { status: string; reason?: string; as_of: string;
  proof_assessment?: string; coverage: null | { required_paise: Paise | null; held_paise: Paise | null;
  shortfall_paise: Paise | null; coverage_end: string | null; term_gap_days: number | null };
  holdings: null | {id:number;amount_paise:Paise;issue_date:string;maturity_date:string;status:string}[];
  open_actions: null | {description:string;responsible_party:string;suggested_only:boolean}[];
  findings: null | {code: string; explanation: string}[] } }
export interface Case { id: number; version: number; instrument_version: number; status: string; path: string; mode: string;
  application_reason?:string;decision_reason?:string;completion_notes?:string;responsible_party?:string;
  documents?:{id:number;name:string;kind:string;page_count:number|null;download_path:string}[];
  history?:{action:string;reason:string;at:string}[];history_has_more?:boolean;
  monitoring_active: boolean; next_action: string; readiness: Assessment | null;
  actions: Record<string, boolean>; clearances: {unit: string; status: string; reason: string; evidence_ref: string; can_decide: boolean}[];
  penalties: {id: number; kind: string; base_paise: Paise; amount_paise: Paise; rate_bps: number; clause: string; status: string; reason: string}[];
  penalty_review_complete: boolean; letter: null | {serial: string; kind: string; revoked: boolean; unsigned_demo: boolean} }
export interface PublicRecord {serial: string; issue_date: string; institution_name: string; kind: string; status: 'ISSUED'|'REVOKED'}
export function publicRecord(value: unknown): PublicRecord {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Unavailable');
  const record = value as Record<string, unknown>;
  const keys = ['serial','issue_date','institution_name','kind','status'];
  if (Object.keys(record).length !== keys.length || keys.some(k => typeof record[k] !== 'string')) throw new Error('Unavailable');
  if (!['ISSUED','REVOKED'].includes(record.status as string) || !['NOC','SANCTION_ORDER'].includes(record.kind as string)) throw new Error('Unavailable');
  return record as unknown as PublicRecord;
}
