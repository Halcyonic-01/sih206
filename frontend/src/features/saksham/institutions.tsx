import { t as tr, useLanguage } from '@/i18n';
import * as React from 'react';
import { Alert, Empty, Table } from 'antd';
import { PageHeader } from '@/components/PageHeader';
import { Panel, StatCard, SummaryList } from '@/components/Panel';
import { StatusTag } from '@/components/StatusTag';
import { formatDate } from '@/lib/format';
import { findingLabel, humanize } from '@/lib/labels';
import {api, Approval, Institution, Obligation, ObligationDetail, Page, Transport, money} from './client';
import {ErrorBox, Loading, Notice, useRemote} from './shared';
import {DepositReadiness} from './DepositReadiness';

function Pager({page, setPage, count, label}: {page: number; setPage: (n: number) => void; count?: number; label: string}) {
  useLanguage();
  if (page === 1 && (count ?? 0) <= 25) return null;
  return <nav aria-label={tr("{0} pages", {"0": (label)})}>
    <button disabled={page === 1} onClick={() => setPage(page - 1)}>{tr("Previous  ")}{label}</button>
    <button disabled={page * 25 >= (count ?? 0)} onClick={() => setPage(page + 1)}>{tr("Next  ")}{label}</button>
  </nav>;
}

export function InstitutionList({client, identityKey, onSelect}: {client: Transport; identityKey: string; onSelect: (id: number) => void}) {
  useLanguage();
  const [q, setQ] = React.useState('');
  const [page, setPage] = React.useState(1);
  const remote = useRemote<Page<Institution>>(client, `institutions?q=${encodeURIComponent(q)}&page=${page}`, identityKey);
  return <section>
    <PageHeader title={tr("Institutions")} subtitle={tr("Profiles, programme approvals and the deposit each institution owes.")} />
    <Notice />
    <label>{tr("Search institutions  ")}<input value={q} maxLength={100} onChange={e => {setQ(e.target.value); setPage(1);}} /></label>
    {remote.error ? <ErrorBox error={remote.error} /> : !remote.data ? <Loading /> : <>
      {!remote.data.results.length ? <p>{tr("No visible institutions.")}</p> : <ul className="record-list">{remote.data.results.map(i =>
        <li key={i.id} className="record-card">
          <div className="record-card__top">
            <button type="button" className="record-card__ref" onClick={() => onSelect(i.id)}>{i.name}</button>
            <span className="muted">{i.code}</span>
          </div>
          {i.profile && <dl className="record-card__meta">
            <div><dt>AICTE ID</dt><dd>{i.profile.aicte_id}</dd></div>
            <div><dt>{tr("Type")}</dt><dd>{humanize(i.profile.institution_type)}</dd></div>
            <div><dt>{tr("Region")}</dt><dd>{i.profile.region} · {i.profile.state}</dd></div>
          </dl>}
        </li>)}</ul>}
      <Pager page={page} setPage={setPage} count={remote.data.count} label={tr("page")} /></>}
  </section>;
}

export function InstitutionDetail({client, identityKey, institutionId, actions, focusObligationId, focusAction}: {client: Transport; identityKey: string; institutionId: number; actions?: React.ReactNode; focusObligationId?: number | null; focusAction?: string | null}) {
  useLanguage();
  return <InstitutionDetailBody key={`${identityKey}:${institutionId}`} client={client} identityKey={identityKey} institutionId={institutionId} actions={actions} focusObligationId={focusObligationId} focusAction={focusAction} />;
}
function InstitutionDetailBody({client, identityKey, institutionId, actions, focusObligationId, focusAction}: {client: Transport; identityKey: string; institutionId: number; actions?: React.ReactNode; focusObligationId?: number | null; focusAction?: string | null}) {
  useLanguage();
  const base = `institutions/${institutionId}`;
  const [programmePage, setProgrammePage] = React.useState(1);
  const [obligationPage, setObligationPage] = React.useState(1);
  const detail = useRemote<Institution>(client, base, identityKey);
  const programmes = useRemote<Page<Approval>>(client, `${base}/programme-approvals?page=${programmePage}`, identityKey);
  const obligations = useRemote<Page<Obligation>>(client, `${base}/obligations?page=${obligationPage}`, identityKey);
  // Gate all child rendering on successful parent scope resolution.
  if (detail.error) return <ErrorBox error={detail.error} />;
  if (!detail.data) return <Loading />;
  const profile = detail.data.profile;
  return <section key={`${identityKey}:${institutionId}`}>
    <PageHeader title={detail.data.name} subtitle={tr("Institution code {0}", {"0": (detail.data.code)})} extra={actions}
      breadcrumb={[{label: tr("Institutions"), to: '/institutions'}, {label: detail.data.name}]} />
    <Notice />
    <div className="stack stack--lg">
      <DepositReadiness client={client} identityKey={identityKey} institutionId={institutionId}
        focusObligationId={focusObligationId} renderTarget={id => <ObligationCard client={client} identityKey={identityKey}
          obligationId={id} focusAction={focusAction} />} />
      <Panel title={tr("Profile")}>
        {profile ? <SummaryList items={[
          {label: 'AICTE ID', value: profile.aicte_id}, {label: tr("Trust"), value: profile.trust_name},
          {label: tr("Institution type"), value: humanize(profile.institution_type)}, {label: tr("Region / state"), value: `${profile.region} / ${profile.state}`},
          {label: tr("Contact email"), value: profile.contact_email}, {label: tr("Profile status"), value: profile.status ? <StatusTag value={profile.status} /> : null},
        ]} /> : <p>{tr("Institution profile unavailable.")}</p>}
      </Panel>
      <Panel title={tr("Programme approvals")} flush>
        {programmes.error ? <div className="panel__body"><ErrorBox error={programmes.error} /></div> : !programmes.data ? <div className="panel__body"><Loading /></div> :
          <Table rowKey="id" size="middle" scroll={{x: 520}} pagination={false} dataSource={programmes.data.results}
            locale={{emptyText: tr("No programme approvals recorded.")}} columns={[
            {title: tr("Programme"), dataIndex: 'programme', render: (v: string) => humanize(v)}, {title: tr("Level"), dataIndex: 'level'},
            {title: tr("Approval reference"), dataIndex: 'loa_ref'}, {title: tr("Approved on"), dataIndex: 'approved_on', render: (v: string) => formatDate(v)}]} />}
        <div className="panel__body" style={{paddingTop: 0}}><Pager page={programmePage} setPage={setProgrammePage} count={programmes.data?.count} label={tr("programmes")} /></div>
      </Panel>
      {!focusObligationId && <div className="stack">
        <h2 style={{marginBottom: 0}}>{tr("Obligations")}</h2>
        {obligations.error ? <ErrorBox error={obligations.error} /> : !obligations.data ? <Loading /> :
          obligations.data.results.length ? obligations.data.results.map(o => <ObligationCard key={o.id} client={client} identityKey={identityKey} obligationId={o.id} />) : <p>{tr("No obligations recorded.")}</p>}
        <Pager page={obligationPage} setPage={setObligationPage} count={obligations.data?.count} label={tr("obligations")} />
      </div>}
    </div>
  </section>;
}

export function ObligationCard({client, identityKey, obligationId, focusAction}: {client: Transport; identityKey: string; obligationId: number; focusAction?: string | null}) {
  useLanguage();
  const remote = useRemote<ObligationDetail>(client, `obligations/${obligationId}`, identityKey);
  if (remote.error) return <ErrorBox error={remote.error} />;
  if (!remote.data) return <Loading />;
  const item = remote.data, coverage = item.assessment.coverage;
  const shortfall = coverage?.shortfall_paise;
  const gap = typeof shortfall === 'string' ? Number(shortfall) > 0 : (shortfall ?? 0) > 0;
  return <article>
    <div className="panel__head" style={{padding: 0}}>
      <h3 style={{margin: 0}}>{tr("Obligation  ")}{item.id}</h3>
      <span className="cluster"><StatusTag value={item.status} /><span className="muted">{tr("Basis:  ")}{humanize(item.basis)}</span></span>
    </div>
    <div className="stat-grid stat-grid--three" style={{margin: '16px 0'}}>
      <StatCard label={tr("Required")} value={money(item.required_paise)} tone="info" />
      <StatCard label={tr("Held")} value={money(coverage?.held_paise)} tone="success" />
      <StatCard label={tr("Shortfall")} value={money(coverage?.shortfall_paise)} tone={gap ? 'danger' : 'neutral'} />
    </div>
    <div className="table-scroll"><table className="data-table"><caption>{tr("Coverage against the obligation term")}</caption><thead><tr><th>{tr("Term start")}</th><th>{tr("Term end")}</th><th>{tr("Continuous coverage through")}</th></tr></thead>
      <tbody><tr><td>{item.term_start ? formatDate(item.term_start) : tr("Unavailable")}</td><td>{item.term_end ? formatDate(item.term_end) : tr("Unavailable")}</td><td>{coverage?.coverage_end ? formatDate(coverage.coverage_end) : tr("Unavailable")}</td></tr></tbody></table></div>
    <p className="muted">{tr("Assessed on  ")}{formatDate(item.assessment.as_of)}. {item.assessment.status === 'UNAVAILABLE' ? tr("Coverage unavailable; source integration required.") : tr("Draft assessment for human review.")}</p>
    <div className="stack">
      {item.assessment.findings?.map(f => <Alert key={f.code} type="warning" showIcon message={findingLabel(f.code)} description={f.explanation} />)}
      {item.assessment.findings?.length === 0 && <Alert type="success" showIcon message={tr("No findings in the available draft assessment.")} />}
    </div>
    <ProofReceipts client={client} item={item} focus={focusAction === 'receipts'} onSaved={() => {remote.reload(); window.dispatchEvent(new Event('pramaan:readiness-changed'));}} />
    <div className="table-scroll"><table className="data-table"><caption>{tr("Scoped holding timeline")}</caption><thead><tr><th>{tr("Holding")}</th><th>{tr("Issue date")}</th><th>{tr("Maturity")}</th><th>{tr("Amount")}</th><th>{tr("Review state")}</th></tr></thead>
      <tbody>{item.assessment.holdings?.map(h => <tr key={h.id}><td>{h.id}</td><td>{formatDate(h.issue_date)}</td><td>{formatDate(h.maturity_date)}</td><td>{money(h.amount_paise)}</td><td><StatusTag value={h.status} /></td></tr>)}</tbody></table></div>
    {item.assessment.holdings == null && <p>{tr("Holding timeline unavailable.")}</p>}
    <h4>{tr("Suggested follow-up")}</h4>
    {item.assessment.open_actions == null ? <p>{tr("Follow-up assessment unavailable.")}</p> : item.assessment.open_actions.length === 0 ? <p className="muted">{tr("Nothing to follow up.")}</p> :
      <ul>{item.assessment.open_actions.map((a, i) => <li key={i}>{tr(a.description)} <span className="muted">· {a.responsible_party}{tr(". Suggested only; no task assigned or notification delivered.")}</span></li>)}</ul>}
  </article>;
}

/** Deposit proof and Affidavit-3 receipt (APH 2.25(f)): shown to everyone, recorded by an officer. */
function ProofReceipts({client, item, onSaved, focus}: {client: Transport; item: ObligationDetail; onSaved: () => void; focus?: boolean}) {
  useLanguage();
  const review = item.proof_review;
  const [payment, setPayment] = React.useState(review?.payment_proof_on ?? '');
  const [affidavit, setAffidavit] = React.useState(review?.affidavit_on ?? '');
  const [reason, setReason] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<unknown>();
  async function save(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(undefined);
    try {
      await client.post(api(`obligations/${item.id}/proof-receipts`), {version: item.version,
        payment_proof_on: payment || null, affidavit_on: affidavit || null, reason});
      setReason(''); onSaved();
    } catch (failure) {setError(failure);} finally {setBusy(false);}
  }
  return <section aria-label={tr("Proof receipts")}><h4>{tr("Deposit proof and Affidavit-3")}</h4>
    <p>{tr("Intimation date:  ")}{item.intimation_date ? formatDate(item.intimation_date) : tr("Not recorded")}{tr(". Proof assessment:  ")}{item.assessment.proof_assessment ?? 'Unavailable'}
      {item.assessment.proof_assessment !== 'AVAILABLE' && ' (an officer has not yet recorded the receipt review, or the intimation date is missing)'}.</p>
    {review ? <p>{tr("Officer review by  ")}{review.reviewed_by} {tr("  on  ")}{new Date(review.reviewed_at).toLocaleDateString('en-IN', {timeZone: 'Asia/Kolkata'})}{tr(": payment proof ")}{review.payment_proof_on ? tr("received {0}", {"0": (review.payment_proof_on)}) : tr("not received")}{tr(", Affidavit-3 ")}{review.affidavit_on ? tr("received {0}", {"0": (review.affidavit_on)}) : tr("not received")}.</p> : <p>{tr("No officer receipt review yet.")}</p>}
    {item.actions?.can_record_proof_receipts && <form onSubmit={save}><fieldset disabled={busy}><legend>{tr("Record receipt review")}</legend>
      <label>{tr("Payment proof received on  ")}<input autoFocus={focus} type="date" value={payment} onChange={e => setPayment(e.target.value)} /></label>
      <label>{tr("Affidavit-3 received on  ")}<input type="date" value={affidavit} onChange={e => setAffidavit(e.target.value)} /></label>
      <p className="muted">{tr("Leave a date empty if that document has not been received.")}</p>
      <label>{tr("Reason  ")}<textarea required maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <button disabled={!reason.trim()}>{tr("Record receipt review")}</button></fieldset></form>}
    {!!error && <ErrorBox error={error} />}
  </section>;
}

type Crumbs = {label: string; to?: string}[];
export function Calculator({client, identityKey, institutionId, breadcrumb}: {client: Transport; identityKey: string; institutionId: number; breadcrumb?: Crumbs}) {
  useLanguage();
  return <CalculatorBody key={`${identityKey}:${institutionId}`} client={client} identityKey={identityKey} institutionId={institutionId} breadcrumb={breadcrumb} />;
}
function CalculatorBody({client, identityKey, institutionId, breadcrumb}: {client: Transport; identityKey: string; institutionId: number; breadcrumb?: Crumbs}) {
  useLanguage();
  const rules = useRemote<Page<{id: number; code: string; version: number}>>(client, 'rules', identityKey);
  const [rule, setRule] = React.useState('');
  const [rows, setRows] = React.useState([{programme: 'MANAGEMENT', level: 'PG', land_tenure: 'OWNED', building_tenure: 'OWNED'}]);
  const [result, setResult] = React.useState<{required_paise: number; source_clause: string; rule_code: string; rule_version: number; as_of: string} | null>(null);
  const [error, setError] = React.useState<unknown>();
  const [busy, setBusy] = React.useState(false);
  const generation = React.useRef(0);
  function invalidate() {generation.current++; setResult(null); setError(undefined);}
  function update(index: number, field: string, value: string) {invalidate(); setRows(rows.map((r, i) => i === index ? {...r, [field]: value} : r));}
  React.useEffect(() => () => {generation.current++;}, []);
  async function calculate(e: React.FormEvent) {
    e.preventDefault(); const current = ++generation.current; setBusy(true); setError(undefined);
    try {
      const r = await client.post<NonNullable<typeof result>>(api('calculator'), {institution_id: institutionId, rule_set_id: Number(rule), approvals: rows});
      if (current === generation.current) setResult(r);
    } catch (failure) {if (current === generation.current) setError(failure);} finally {setBusy(false);}
  }
  return <section>
    <PageHeader title={tr("Requirement calculator")} breadcrumb={breadcrumb} subtitle={tr("Preview the deposit an institution would owe for a set of programmes. Nothing is saved.")} />
    <Notice />
    {!!rules.error && <ErrorBox error={rules.error} />} {!rules.error && !rules.data && <Loading />}
    {rules.data?.results.length === 0 && <p>{tr("No rule versions available. A preview cannot be calculated.")}</p>}
    <form onSubmit={calculate}><fieldset disabled={busy}><legend>{tr("Programmes")}</legend>
      <label>{tr("Rule version  ")}<select required value={rule} onChange={e => {invalidate(); setRule(e.target.value);}}><option value="">{tr("Select explicit rule")}</option>
        {rules.data?.results.map(r => <option key={r.id} value={r.id}>{r.code} {tr("  v")}{r.version}</option>)}</select></label>
      {rows.map((row, index) => <fieldset key={index}><legend>{tr("Programme  ")}{index + 1}</legend>
        <label>{tr("Programme code  ")}<input required value={row.programme} onChange={e => update(index, 'programme', e.target.value)} /></label>
        <label>{tr("Level  ")}<select value={row.level} onChange={e => update(index, 'level', e.target.value)}>{['DIPLOMA', 'UG', 'PG'].map(x => <option key={x}>{x}</option>)}</select></label>
        <label>{tr("Land tenure  ")}<select value={row.land_tenure} onChange={e => update(index, 'land_tenure', e.target.value)}>{['OWNED', 'LEASED'].map(x => <option key={x}>{x}</option>)}</select></label>
        <label>{tr("Building tenure  ")}<select value={row.building_tenure} onChange={e => update(index, 'building_tenure', e.target.value)}>{['OWNED', 'LEASED'].map(x => <option key={x}>{x}</option>)}</select></label>
        <button type="button" disabled={rows.length === 1} onClick={() => {invalidate(); setRows(rows.filter((_, i) => i !== index));}}>{tr("Remove programme  ")}{index + 1}</button>
      </fieldset>)}
      <button type="button" disabled={rows.length >= 100} onClick={() => {invalidate(); setRows([...rows, {programme: '', level: 'UG', land_tenure: 'OWNED', building_tenure: 'OWNED'}]);}}>{tr("Add programme")}</button>
      <button className="primary" disabled={!rule}>{tr("Calculate preview")}</button></fieldset></form>
    {!!error && <ErrorBox error={error} />}
    {result && <Panel title={tr("Required deposit")}>
      <p className="stat__value" aria-live="polite">{money(result.required_paise)}</p>
      <p className="muted">{tr("Assessed on  ")}{formatDate(result.as_of)} {tr("  using  ")}{result.rule_code} {tr("  v")}{result.rule_version}{tr(", clause  ")}{result.source_clause}{tr(". Draft, for human review only.")}</p>
    </Panel>}
    {!result && <p aria-live="polite" className="sr-only">{busy ? tr("Calculating") : ''}</p>}
    {rules.data && rules.data.results.length > 0 && !result && !error && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={tr("The result appears here.")} />}
  </section>;
}
