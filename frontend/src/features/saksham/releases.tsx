import * as React from 'react';
import { Alert, Table, Timeline } from 'antd';
import { CheckCircleFilled, CloseCircleFilled } from '@ant-design/icons';
import { PageHeader } from '@/components/PageHeader';
import { Panel, SummaryList } from '@/components/Panel';
import { StatusTag } from '@/components/StatusTag';
import { formatDate, formatDateTime } from '@/lib/format';
import { humanize, RELEASE_PATH_LABELS } from '@/lib/labels';
import {api, Case, Clearance, ClearanceEvidence, Page, PublicRecord, publicRecord, Transport, money, paise, Failure} from './client';
import {ClearancePdf} from './ClearanceEvidence';
import {ErrorBox, Loading, Notice, Readiness, useRemote} from './shared';

export interface ReleaseInputs {
  instrumentId: number; obligationId: number; instrumentVersion: number;
  // Supplied by the server (eligibility, questionnaire, document checklist); never invented in the browser.
  canRequest: boolean;
  questionnaire?: {version: string; questions: {id: string; label: string}[]};
  documentPath?: string; onPathChange?: (path: string) => void;
  documentsReady: boolean; documents: React.ReactNode;
}

const PATHS = Object.entries(RELEASE_PATH_LABELS);

export function ReleaseWizard({client, identityKey, inputs, onCreated}: {client: Transport; identityKey: string; inputs: ReleaseInputs; onCreated: (id: number) => void}) {
  return <WizardBody key={`${identityKey}:${inputs.instrumentId}:${inputs.instrumentVersion}:${inputs.questionnaire?.version ?? ''}`} client={client} inputs={inputs} onCreated={onCreated} />;
}
function WizardBody({client, inputs, onCreated}: {client: Transport; inputs: ReleaseInputs; onCreated: (id: number) => void}) {
  const [step, setStep] = React.useState(0);
  const [path, setPath] = React.useState('TERM_COMPLETE');
  const [answers, setAnswers] = React.useState<Record<string, boolean | null>>({});
  const [reason, setReason] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<unknown>();
  const title = React.useRef<HTMLHeadingElement>(null);
  React.useEffect(() => {title.current?.focus();}, [step]);
  const questionnaire = inputs.questionnaire;
  const answered = !!questionnaire?.questions.length && questionnaire.questions.every(q => typeof answers[q.id] === 'boolean');
  const documentsReady = inputs.documentsReady && inputs.documentPath === path;
  const nextAllowed = step === 0 ? !!reason.trim() : step === 1 ? answered : documentsReady;
  async function submit() {
    if (!inputs.canRequest || !answered || !documentsReady || !reason.trim()) return;
    setBusy(true); setError(undefined);
    try {
      const result = await client.post<Case>(api('releases'), {instrument_id: inputs.instrumentId, obligation_id: inputs.obligationId,
        instrument_version: inputs.instrumentVersion, path, declarations: answers, reason, template_ref: questionnaire?.version});
      onCreated(result.id);
    } catch (e) {setError(e);} finally {setBusy(false);}
  }
  const pathLabel = RELEASE_PATH_LABELS[path] ?? humanize(path);
  return <section>
    <PageHeader title="Request release" subtitle="Four steps: choose the path, answer the declarations, check the documents, then submit." />
    <Notice />
    <ol aria-label="Release request steps">{['Path', 'Declarations', 'Documents', 'Review'].map((s, i) => <li key={s} aria-current={i === step ? 'step' : undefined}>{s}</li>)}</ol>
    <Panel>
      <h2 ref={title} tabIndex={-1} style={{marginTop: 0}}>{['Select path', 'Record declarations', 'Review documents', 'Review and submit'][step]}</h2>
      {!!error && <ErrorBox error={error} />}
      <fieldset disabled={busy} style={{border: 0, padding: 0}}><legend className="sr-only">Release request</legend>
        {step === 0 && <>
          <label>Path <select value={path} onChange={e => {setPath(e.target.value); setAnswers({}); inputs.onPathChange?.(e.target.value);}}>
            {PATHS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label>Reason <textarea required maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></label></>}
        {step === 1 && (!questionnaire ? <p role="alert">Declaration template unavailable. Obtain the approved Affidavit-6 questionnaire; no questions have been invented.</p> : <>
          <p className="muted">Affidavit-6 questionnaire, version {questionnaire.version}. Answer every question.</p>
          {questionnaire.questions.map(q => <label key={q.id}>{q.label}<select value={answers[q.id] == null ? '' : String(answers[q.id])}
            onChange={e => setAnswers({...answers, [q.id]: e.target.value === '' ? null : e.target.value === 'true'})}>
            <option value="">Not answered</option><option value="true">Yes</option><option value="false">No</option></select></label>)}</>)}
        {step === 2 && <>
          <p>Path: {pathLabel}. The documents below must be uploaded and readable before you can continue.</p>
          {inputs.documents ?? <p role="alert">Document upload is unavailable.</p>}
          {!documentsReady && <p role="alert">Required documents are incomplete, out of date for this path, or unavailable.</p>}</>}
        {step === 3 && <>
          <SummaryList items={[{label: 'Path', value: pathLabel}, {label: 'Reason', value: reason}]} />
          <p className="muted">Submitting asks for human review. Clearances, penalties, approval, the letter and completion are separate steps.</p>
          {!inputs.canRequest && <p role="alert">You cannot submit this request: the record is not eligible or the source is unavailable.</p>}
          <button className="primary" disabled={!inputs.canRequest || !answered || !documentsReady} onClick={submit}>Submit release request</button></>}
        <div style={{marginTop: 16}}>
          <button disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
          {step < 3 && <button className="primary" disabled={!nextAllowed} onClick={() => setStep(step + 1)}>Next</button>}
        </div>
      </fieldset>
    </Panel>
  </section>;
}

export function ReleaseCase({client, identityKey, caseId}: {client: Transport; identityKey: string; caseId: number}) {
  return <CaseBody key={`${identityKey}:${caseId}`} client={client} identityKey={identityKey} caseId={caseId} />;
}
function CaseBody({client, identityKey, caseId}: {client: Transport; identityKey: string; caseId: number}) {
  const remote = useRemote<Case>(client, `releases/${caseId}`, identityKey);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<unknown>();
  const [reason, setReason] = React.useState('');
  const [file, setFile] = React.useState<File>();
  const [refund, setRefund] = React.useState('');
  const [penalty, setPenalty] = React.useState('premature_encashment');
  const [base, setBase] = React.useState('');
  const [summary, setSummary] = React.useState<{status: string; cached: boolean; label: string; summary?: string; risk_flags?: {field: string; severity: string; message: string}[]; detail?: string}>();
  async function mutate(action: string, extra: Record<string, unknown> = {}, multipart?: FormData) {
    if (!remote.data || !reason.trim() || busy) return;
    setBusy(true); setError(undefined); const current = remote.data;
    try {
      const payload = multipart ?? {version: current.version, reason,
        ...(['approve', 'reject'].includes(action) ? {instrument_version: current.instrument_version} : {}), ...extra};
      await client.post(api(`releases/${caseId}/${action}`), payload); setReason(''); setFile(undefined);
    } catch (e) {setError(e);} finally {remote.reload(); setBusy(false);}
  }
  if (remote.error) return <ErrorBox error={remote.error} />;
  if (!remote.data) return <Loading />;
  const item = remote.data;
  async function getSummary() {
    if (busy) return; setBusy(true); setError(undefined);
    try {setSummary(await client.post(api(`releases/${caseId}/ai-summary`), {version: item.version}));} catch (e) {setError(e);} finally {setBusy(false);}
  }
  const pathLabel = RELEASE_PATH_LABELS[item.path] ?? humanize(item.path);
  return <section>
    <PageHeader title={`Release case ${item.id}`} breadcrumb={[{label: 'Release cases', to: '/releases'}, {label: `Case ${item.id}`}]}
      subtitle={<span className="cluster"><StatusTag value={item.status} /><span className="muted">{pathLabel} · {item.mode}</span></span>} />
    <Notice />
    <div className="stack stack--lg">
      {item.status === 'APPROVED' && <Alert type="success" showIcon message="Release authorized; completion pending." description="Monitoring continues until completion is recorded with new evidence." />}
      <Panel title="Case summary">
        <SummaryList items={[
          {label: 'Monitoring', value: item.monitoring_active ? 'Active' : 'Ended by recorded completion'},
          {label: 'Next step', value: item.next_action}, {label: 'Responsible', value: item.responsible_party ?? 'Unavailable'},
          {label: 'Application reason', value: item.application_reason ?? 'Unavailable'},
          {label: 'Decision reason', value: item.decision_reason}, {label: 'Completion notes', value: item.completion_notes}]} />
      </Panel>
      <div className="two-col">
        <Panel title="Readiness for human review"><Readiness value={item.readiness} /></Panel>
        <Panel title="Documents">
          {item.documents ? (item.documents.length === 0 ? <p className="muted">No documents.</p> : <ul>{item.documents.map(d => <li key={d.id}>
            {d.name} <span className="muted">· {humanize(d.kind)} · {d.page_count == null ? 'pages unknown' : `${d.page_count} ${d.page_count === 1 ? 'page' : 'pages'}`}</span>{' '}
            {/^\/(?!\/)/.test(d.download_path) && <button disabled={busy} onClick={() => client.download(d.download_path).catch(setError)}>Download {d.name}</button>}</li>)}</ul>) : <p>Document list unavailable.</p>}
        </Panel>
      </div>
      {!!error && <ErrorBox error={error} />}
      <Panel title="AI summary">
        {item.actions.can_ai_summary ? <>
          <p className="muted">Advisory only. It cannot approve, reject or change this case.</p>
          {item.ai_summary_enabled === false ? <p>AI summary is off. Continue manual release review.</p> : <button disabled={busy} onClick={() => void getSummary()}>Generate AI summary</button>}
        </> : <p className="muted">Available to the assigned clearance units and the independent authority.</p>}
        {summary && <div role="status"><p><strong>{summary.label}</strong></p>
          {summary.status === 'success' ? <><p>{summary.summary}</p>{summary.cached && <p className="muted">Saved result for this case version.</p>}
            <ul>{summary.risk_flags?.map((flag, i) => <li key={i}><strong>{humanize(flag.severity)}</strong> · {flag.field}: {flag.message}</li>)}</ul></> : <p>{summary.detail}</p>}</div>}
      </Panel>
      <Panel title="Clearances" flush>
        <Table rowKey="unit" size="middle" scroll={{x: 520}} pagination={false} dataSource={item.clearances} locale={{emptyText: 'No clearances required.'}} columns={[
          {title: 'Unit', dataIndex: 'unit'}, {title: 'Status', dataIndex: 'status', render: (v: string) => <StatusTag value={v} />},
          {title: 'Reason', dataIndex: 'reason', render: (v: string) => v || '—'},
          {title: 'Review and evidence', render: (_, t: Clearance) => <>
            <p>{t.reviewer || 'No reviewer'} · {t.decided_at ? formatDateTime(t.decided_at) : 'Decision time not recorded'}</p>
            <p>{t.evidence_ref || 'No reference'}</p>
            {t.evidence ? <ClearancePdf key={t.evidence.id} evidence={t.evidence} /> :
              <p>{t.evidence_state === 'LINKED_PDF' ? 'Protected PDF — access restricted to reviewing roles.' : 'Reference only — no linked PDF.'}</p>}
          </>}]} />
      </Panel>
      <Panel title="Penalties">
        {item.penalties.length === 0 ? <p className="muted">No penalties proposed.</p> : <ul>{item.penalties.map(p => <li key={p.id}>{humanize(p.kind)}: {money(p.amount_paise)} <StatusTag value={p.status} /> <span className="muted">· clause {p.clause}</span>
          {item.actions.can_review_penalties && p.status === 'PROPOSED' && <button disabled={busy || !reason.trim()} onClick={() => mutate('penalties', {confirm_id: p.id})}>Confirm reviewed proposal</button>}</li>)}</ul>}
        <p className="muted">Officer review complete: {item.penalty_review_complete ? 'Yes' : 'No'}. Confirming a penalty does not prove payment or authorise a deduction.</p>
      </Panel>
      <Panel title="Decision and actions">
        <fieldset disabled={busy} style={{border: 0, padding: 0}}><legend className="sr-only">Human action and reason</legend>
          <label>Reason / completion notes <textarea required maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></label>
          {item.actions.can_review_penalties && <>
            <label>Penalty kind <select value={penalty} onChange={e => setPenalty(e.target.value)}>{['premature_encashment', 'closure_lapsed', 'closure_six_years'].map(k => <option key={k} value={k}>{humanize(k)}</option>)}</select></label>
            <label>Reviewed penalty base (INR) <input inputMode="decimal" value={base} onChange={e => setBase(e.target.value)} /></label>
            <button disabled={!reason.trim() || !base} onClick={() => {try {void mutate('penalties', {kind: penalty, base_paise: paise(base)});} catch (e) {setError(e);}}}>Propose penalty for review</button>
            <button className="primary" disabled={!reason.trim()} onClick={() => mutate('penalties')}>Record officer checklist and penalty review complete</button></>}
          {item.actions.can_approve && <button className="primary" disabled={!reason.trim()} onClick={() => mutate('approve')}>Record authority authorization</button>}
          {item.actions.can_reject && <button disabled={!reason.trim()} onClick={() => mutate('reject')}>Record authority rejection</button>}
          {item.actions.can_issue && <button className="primary" disabled={!reason.trim()} onClick={() => mutate('issue')}>Issue letter (unsigned)</button>}
          {item.actions.can_revoke && <button disabled={!reason.trim()} onClick={() => mutate('revoke')}>Revoke letter</button>}
        </fieldset>
      </Panel>
      <div className="two-col">
        <Panel title="Letter">
          {item.letter ? <><p><strong>{humanize(item.letter.kind)}</strong> {item.letter.serial} <StatusTag value={item.letter.revoked ? 'REVOKED' : 'ISSUED'} /></p>
            <p className="muted">Not digitally signed. The QR code leads to the public verification page.</p>
            <button onClick={() => client.download(api(`releases/${caseId}/letter`)).catch(setError)}>Download protected letter</button></> : <p className="muted">Not issued.</p>}
        </Panel>
        <Panel title="Completion">
          {item.actions.can_complete ? <fieldset disabled={busy} style={{border: 0, padding: 0}}>
            <label>New completion PDF <input type="file" accept="application/pdf,.pdf" onChange={e => setFile(e.target.files?.[0])} /></label>
            {item.mode === 'RTGS' && <label>Recorded bank/PFMS refund reference <input maxLength={200} value={refund} onChange={e => setRefund(e.target.value)} /></label>}
            <button className="primary" disabled={!file || !reason.trim() || (item.mode === 'RTGS' && !refund.trim())} onClick={() => {
              if (!file) return; const data = new FormData();
              data.set('version', String(item.version)); data.set('instrument_version', String(item.instrument_version)); data.set('notes', reason); data.set('refund_reference', refund); data.set('document', file);
              void mutate('complete', {}, data);}}>Record evidence-backed completion</button></fieldset>
            : <p className="muted">Completion is not available in the current state.</p>}
        </Panel>
      </div>
      <Panel title="Case history">
        <Timeline items={item.history?.map((h, i) => ({key: i, children: <><strong>{humanize(h.action)}</strong>{h.reason && <div>{h.reason}</div>}<small className="muted">{formatDateTime(h.at)} IST</small></>}))} />
        {item.history_has_more && <p className="muted">The latest 100 events are shown; earlier history exists.</p>}
      </Panel>
      <div><button disabled={busy} onClick={remote.reload}>Reload case</button></div>
    </div>
  </section>;
}

interface Task extends Clearance {case_id: number; version: number; due_date: string | null}
export function ClearanceQueue({client, identityKey, onSelect}: {client: Transport; identityKey: string; onSelect: (id: number) => void}) {
  return <QueueBody key={identityKey} client={client} identityKey={identityKey} onSelect={onSelect} />;
}
function QueueBody({client, identityKey, onSelect}: {client: Transport; identityKey: string; onSelect: (id: number) => void}) {
  const [page, setPage] = React.useState(1);
  const remote = useRemote<Page<Task>>(client, `clearance-tasks?page=${page}`, identityKey);
  return <section>
    <PageHeader title="Clearance work" subtitle="Release cases waiting for your unit’s decision." />
    <Notice />
    {!!remote.error && <ErrorBox error={remote.error} />}
    {!remote.error && !remote.data && <Loading />}
    <p>Upload and review a supporting PDF for the specific case before recording your unit’s decision.</p>
    <h2>Cases</h2>
    {remote.data?.results.length === 0 && <p>No assigned clearance work. This does not mean all cases are cleared.</p>}
    <ul className="record-list">{remote.data?.results.map(t => <li key={`${t.case_id}:${t.unit}`} className="record-card">
      <div className="record-card__top"><button type="button" className="record-card__ref" onClick={() => onSelect(t.case_id)}>Case {t.case_id}</button><StatusTag value={t.status} /></div>
      <dl className="record-card__meta"><div><dt>Unit</dt><dd>{t.unit}</dd></div><div><dt>Due</dt><dd>{t.due_date ? formatDate(t.due_date) : 'Unavailable'}</dd></div></dl>
      {t.can_decide ? <ClearanceDecision key={`${t.case_id}:${t.version}`} task={t} client={client} reload={remote.reload} /> :
        t.evidence ? <ClearancePdf evidence={t.evidence} /> : <p>Reference only — no linked PDF.</p>}
    </li>)}</ul>
    <nav aria-label="Task pages"><button disabled={page === 1} onClick={() => setPage(page - 1)}>Previous tasks</button>
      <button disabled={page * 25 >= (remote.data?.count ?? 0)} onClick={() => setPage(page + 1)}>Next tasks</button></nav>
  </section>;
}

function ClearanceDecision({task, client, reload}: {task: Task; client: Transport; reload: () => void}) {
  const base = `releases/${task.case_id}/clearances/${task.unit}`;
  const remote = useRemote<{version: number; results: ClearanceEvidence[]}>(client, `${base}/evidence`, `${task.case_id}:${task.version}`);
  const [file, setFile] = React.useState<File | null>(null);
  const [selected, setSelected] = React.useState<number | null>(null);
  const [reason, setReason] = React.useState('');
  const [reference, setReference] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<unknown>();
  const evidence = remote.data?.results.find(e => e.id === selected);
  async function upload() {
    if (!file || busy) return;
    setBusy(true); setError(undefined);
    const form = new FormData(); form.set('version', String(remote.data?.version ?? task.version)); form.set('document', file);
    try {await client.post(api(`${base}/evidence`), form); reload();}
    catch (e) {setError(e); setBusy(false);}
  }
  async function decide(status: string) {
    if (!evidence || busy) return;
    setBusy(true); setError(undefined);
    try {await client.post(api(base), {version: remote.data?.version ?? task.version, status, reason,
      evidence_ref: reference, evidence_id: evidence.id}); reload();}
    catch (e) {setError(e); setBusy(false);}
  }
  return <fieldset disabled={busy} aria-label={`Decision for case ${task.case_id}`}>
    <legend>Your decision — case {task.case_id}</legend>
    {!!error && <ErrorBox error={error} />}{!!remote.error && <ErrorBox error={remote.error} />}
    {!remote.data && !remote.error && <Loading />}
    <label>Supporting clearance PDF <input type="file" accept="application/pdf" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
    <button disabled={!file || busy || !!remote.error} onClick={() => void upload()}>Upload supporting PDF</button>
    <label>Reviewed supporting PDF <select value={selected ?? ''} onChange={e => setSelected(Number(e.target.value) || null)}>
      <option value="">Select a PDF to review</option>{remote.data?.results.map(e => <option key={e.id} value={e.id}>{e.name} (#{e.id})</option>)}
    </select></label>
    {evidence && <ClearancePdf key={evidence.id} evidence={evidence} />}
    <label>Reason <textarea maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></label>
    <label>Reviewed evidence reference <input maxLength={200} value={reference} onChange={e => setReference(e.target.value)} /></label>
    {task.status !== 'OPEN' && <p>Re-attestation preserves the existing {task.status} decision; the prior review remains in history.</p>}
    {(task.status === 'OPEN' ? ['CLEARED', 'OBJECTION', 'HOLD'] : [task.status]).map(s => <button key={s}
      disabled={busy || !evidence || !reason.trim() || !reference.trim() || !!remote.error}
      onClick={() => void decide(s)}>{s.toLowerCase()}</button>)}
  </fieldset>;
}

export function PublicVerification({client, token}: {client: Transport; token: string}) {
  const remote = useRemote<unknown>(client, `public/verify/${encodeURIComponent(token)}`, token);
  if (remote.error) {
    const status = (remote.error as Failure)?.status;
    return <section><h1>Verify letter</h1>
      <p role="alert">{status === 404 || status === 400 ? 'Verification record unavailable.' : 'Verification service temporarily unavailable.'}</p>
      <button onClick={remote.reload}>Retry</button></section>;
  }
  if (!remote.data) return <Loading />;
  let record: PublicRecord;
  try {record = publicRecord(remote.data);} catch {return <p role="alert">Verification response unavailable.</p>;}
  const revoked = record.status === 'REVOKED';
  return <section className="verify-result">
    <div className={`verify-icon ${revoked ? 'verify-icon--bad' : 'verify-icon--ok'}`} aria-hidden>{revoked ? <CloseCircleFilled /> : <CheckCircleFilled />}</div>
    <h1>{revoked ? 'Revoked — do not rely on this letter' : 'Letter found'}</h1>
    <Notice />
    <SummaryList items={[{label: 'Serial', value: record.serial}, {label: 'Issue date', value: formatDate(record.issue_date)},
      {label: 'Institution', value: record.institution_name}, {label: 'Kind', value: record.kind === 'NOC' ? 'No Objection Certificate' : 'Sanction order'}]} />
    <p className="muted">This confirms that the letter was issued by the portal. It is not a bank confirmation or a digital signature.</p>
  </section>;
}
