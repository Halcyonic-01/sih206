import {useEffect, type ReactNode} from 'react';
import {Link} from 'react-router-dom';
import {t, useLanguage} from '@/i18n';
import {Panel} from '@/components/Panel';
import {formatDate} from '@/lib/format';
import type {Transport} from './client';
import {ErrorBox, Loading, useRemote} from './shared';

interface Item {
  id: string; state: string; reason: string; helper?: string;
  deadline: null | {due_on: string | null; days_remaining: number | null; state: string};
  targets?: {label: string; href: string; record_id?: number; record_reference?: string}[];
}
export interface ReadinessSummary {
  institution_id: number; completed: number; applicable: number; percent: number | null; status: string;
  as_of: string; source_fingerprint: string;
  obligations: {obligation_id: number; completed: number; applicable: number; percent: number | null;
    mode: string; mode_known?: boolean; policy_source: string; items: Item[]}[];
}
const LABELS: Record<string, string> = {accepted_deposit: 'Deposit submitted and accepted', payment_proof: 'Payment proof uploaded',
  affidavit_3: 'Affidavit-3 uploaded', amount_coverage: 'Amount meets the recorded requirement',
  proof_receipt: 'Proof receipt recorded by officer', bank_confirmation: 'Bank confirmation received'};
const STATES: Record<string, string> = {COMPLETE: 'Complete', INCOMPLETE: 'Incomplete', UNKNOWN: 'Unknown',
  NOT_APPLICABLE: 'Not applicable', SIMULATED: 'Simulated', BLOCKED: 'Needs attention'};
export function safeReadinessLink(href: string): boolean {
  return /^\/records(?:\/[1-9]\d*)?(?:\?[^#]*)?$/.test(href) || /^\/institutions\/[1-9]\d*(?:\?[^#]*)?$/.test(href);
}
export function DepositReadiness({client, identityKey, institutionId, focusObligationId, renderTarget}: {
  client: Transport; identityKey: string; institutionId: number; focusObligationId?: number | null;
  renderTarget?: (id: number) => ReactNode;
}) {
  useLanguage();
  const remote = useRemote<ReadinessSummary>(client, `institutions/${institutionId}/readiness`, identityKey);
  useEffect(() => {
    const refresh = () => remote.reload();
    window.addEventListener('focus', refresh); window.addEventListener('pramaan:readiness-changed', refresh);
    return () => {window.removeEventListener('focus', refresh); window.removeEventListener('pramaan:readiness-changed', refresh);};
  }, [remote.reload]);
  const data = remote.data;
  const progress = (value: {completed: number; applicable: number; percent: number | null}, id: string) => <div>
    <p id={id}>{value.percent === null ? t('No applicable steps to measure.') :
      t('{0} of {1} applicable recorded steps complete ({2}%)', {'0': value.completed, '1': value.applicable, '2': value.percent})}</p>
    {value.percent !== null && <progress aria-label={t('Deposit readiness')} aria-describedby={id}
      aria-valuetext={`${value.completed}/${value.applicable} (${value.percent}%)`} value={value.completed}
      max={value.applicable} style={{width: '100%', accentColor: '#153957'}} />}
  </div>;
  return <Panel title={t('Deposit readiness')}>
    <p role="note">{t('Recorded milestones, not regulatory compliance. Uploads and acceptance do not establish bank authenticity.')}</p>
    {remote.error ? <ErrorBox error={remote.error} /> : !data ? <Loading /> : data.institution_id !== institutionId ?
      <ErrorBox error={{status: 404}} /> : <>
      {progress(data, `readiness-${institutionId}`)}
      {!data.obligations.length && <p>{t('No obligations recorded.')}</p>}
      {data.obligations.map(obligation => <details key={obligation.obligation_id} open>
        <summary>{t('Obligation')} {obligation.obligation_id} · {obligation.mode_known === false ? t('Deposit mode unknown') : obligation.mode}</summary>
        <p className="muted">{obligation.policy_source}</p>
        {progress(obligation, `readiness-obligation-${obligation.obligation_id}`)}
        <ul className="record-list">{obligation.items.map(item => <li key={item.id} className="record-card">
          <p><span aria-hidden="true">{item.state === 'COMPLETE' ? '✓' : item.state === 'NOT_APPLICABLE' ? '—' : '○'} </span>
            <strong>{t(LABELS[item.id] || item.id)}</strong> — <span>{t(STATES[item.state] || item.state)}</span></p>
          <p className="muted">{t(item.helper || item.reason)}</p>
          {item.deadline && <p>{item.deadline.due_on ? <>{t('Due on')} {formatDate(item.deadline.due_on)} · {
            item.deadline.days_remaining === 0 ? t('Due today') : (item.deadline.days_remaining ?? 0) < 0 ?
              t('Overdue by {0} days', {'0': Math.abs(item.deadline.days_remaining!)}) :
              t('Due in {0} days', {'0': item.deadline.days_remaining!})}</> : t('Deadline unknown; intimation or policy information is missing.')}</p>}
          <div className="cluster">{item.targets?.filter(target => safeReadinessLink(target.href)).map(target =>
            <Link key={target.href} className="btn" to={target.href}>{t(target.label)}{target.record_reference && <> · {target.record_reference}</>}</Link>)}</div>
        </li>)}</ul>
      </details>)}
      {focusObligationId && (data.obligations.some(row => row.obligation_id === focusObligationId) ?
        renderTarget?.(focusObligationId) : <ErrorBox error={{status: 404}} />)}
    </>}
    <button type="button" onClick={remote.reload}>{t('Refresh readiness')}</button>
  </Panel>;
}
