import { t as tr, useLanguage } from '@/i18n';
import * as React from 'react';
import { Alert } from 'antd';
import { PageHeader } from '@/components/PageHeader';
import { Panel, StatCard } from '@/components/Panel';
import {api, Transport} from './client';
import {ErrorBox, Loading, Notice, useRemote} from './shared';

const REPORTS: [string, string][] = [
  ['pending_verifications', 'Pending independent verification'], ['upcoming_maturities', 'Upcoming maturities'],
  ['missing_documents', 'Missing deposit-mode supporting documents'], ['intervention', 'Known intervention items'], ['released_register', 'Released register']];

export function Reports({client, identityKey}: {client: Transport; identityKey: string}) {
  useLanguage();
  return <ReportsBody key={identityKey} client={client} />;
}
function ReportsBody({client}: {client: Transport}) {
  useLanguage();
  const [kind, setKind] = React.useState('upcoming_maturities');
  const [error, setError] = React.useState<unknown>();
  const [busy, setBusy] = React.useState(false);
  const data = useRemote<{rows: unknown[]; count?: number; limitations: string[]}>(client, `reports/${kind}`, 'report');
  const count = data.data ? (data.data.count ?? data.data.rows.length) : 0;
  return <section>
    <PageHeader title={tr("Reports")} subtitle={tr("Registers of the current records you can see. Each workbook repeats the limitations listed here.")} />
    <Notice />
    <Panel>
      <label>{tr("Report  ")}<select value={kind} onChange={e => setKind(e.target.value)}>{REPORTS.map(([value, label]) => <option key={value} value={value}>{tr(label)}</option>)}</select></label>
      {data.error ? <ErrorBox error={data.error} /> : !data.data ? <Loading /> : <>
        <p role="status"><strong>{count ? tr('{count} matching items.', {count}) : tr("No matching items.")}</strong></p>
        <h3>{tr("Limitations")}</h3>
        <ul aria-label={tr("Report limitations")}>{data.data.limitations.map(text => <li key={text}>{tr(text)}</li>)}</ul></>}
      <button className="primary" disabled={busy || !data.data} onClick={async () => {
        setBusy(true); setError(undefined);
        try {await client.download(api(`reports/${kind}?download=xlsx`));} catch (e) {setError(e);} finally {setBusy(false);}}}>{tr("Download XLSX")}</button>
      {busy && <p role="status">{tr("Preparing download…")}</p>}
      {!!error && <ErrorBox error={error} />}
    </Panel>
  </section>;
}

interface Preview {preview_id: number | null; version?: number; status: string; valid_count: number; row_count: number | null;
  errors: {row: number | null; field: string; code: string}[]; valid_rows: {row: number; values: Record<string, string>}[]}
export function InstitutionImport({client, identityKey}: {client: Transport; identityKey: string}) {
  useLanguage();
  return <ImportBody key={identityKey} client={client} />;
}
function ImportBody({client}: {client: Transport}) {
  useLanguage();
  const [file, setFile] = React.useState<File>();
  const [preview, setPreview] = React.useState<Preview>();
  const [reason, setReason] = React.useState('');
  const [done, setDone] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<unknown>();
  async function inspect(e: React.FormEvent) {
    e.preventDefault(); if (!file) return; setBusy(true); setError(undefined); setDone(false);
    try {const data = new FormData(); data.set('file', file); setPreview(await client.post<Preview>(api('imports/institutions/preview'), data));}
    catch (e) {setError(e); setPreview(undefined);} finally {setBusy(false);}
  }
  async function commit() {
    if (!preview?.preview_id || !reason.trim()) return; setBusy(true); setError(undefined);
    try {await client.post(api(`imports/institutions/${preview.preview_id}/commit`), {version: preview.version, reason}); setDone(true); setPreview(undefined);}
    catch (e) {setError(e); setPreview(undefined);} finally {setBusy(false);}
  }
  return <section>
    <PageHeader title={tr("Import institutions")} subtitle={tr("Officers only. Preview the file first; every row must be valid, and existing institutions are never overwritten.")} />
    <Notice />
    <Panel title={tr("1. Choose a CSV file")}>
      <form onSubmit={inspect}><fieldset disabled={busy} style={{border: 0, padding: 0}}><legend className="sr-only">{tr("CSV preview")}</legend>
        <label>{tr("SIMULATED CSV (up to 1 MiB)  ")}<input type="file" accept=".csv,text/csv" required
          onChange={e => {setFile(e.target.files?.[0]); setPreview(undefined); setDone(false); setError(undefined);}} /></label>
        <button className="primary">{tr("Preview")}</button></fieldset></form>
      {busy && <p role="status">{tr("Processing import…")}</p>}
      {!!error && <ErrorBox error={error} />}
      <div aria-live="polite">{done && <Alert type="success" showIcon message={tr("Import committed. New institution identities were created.")} />}</div>
    </Panel>
    {preview && <Panel title={tr("2. Preview: {0}", {"0": (preview.status === 'VALID' ? tr("ready to import") : tr("needs fixing"))})}>
      <p>{preview.valid_count} {tr("  valid rows of  ")}{preview.row_count ?? 'unknown'}.</p>
      {preview.errors.length > 0 && <ul>{preview.errors.map((e, i) => <li key={i}>{tr("Row  ")}{e.row ?? 'file'}, {e.field}: {e.code}</li>)}</ul>}
      <div className="table-scroll"><table className="data-table"><caption>{tr("Candidate institutions")}</caption><thead><tr><th>{tr("Row")}</th><th>{tr("Code")}</th><th>{tr("Name")}</th></tr></thead><tbody>{preview.valid_rows.map(r =>
        <tr key={r.row}><td>{r.row}</td><td>{r.values.institution_code}</td><td>{r.values.institution_name}</td></tr>)}</tbody></table></div>
      <label>{tr("Import reason  ")}<textarea maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} /></label>
      <button className="primary" disabled={busy || preview.status !== 'VALID' || !preview.preview_id || !reason.trim()} onClick={commit}>{tr("Confirm complete-file import")}</button>
    </Panel>}
  </section>;
}

interface KpiResult {submission_to_acceptance: {sample_count: number; median_seconds: string | null; p90_seconds: string | null};
  correction_cycles: {mean_per_accepted_record: string | null};
  renewed_on_time: {percentage_bps: number | null}; limitations?: string[];
  data_quality?: {incomplete_process_histories: number}; confirmed_share: {percentage_bps: number | null; unknown_count?: number}}

/** 93784 -> "1 d 2 h"; the API sends seconds as a decimal string. */
function duration(value: string | null | undefined): string {
  if (value == null) return 'Unavailable';
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) return 'Unavailable';
  if (seconds < 1) return '< 1 s';
  const d = Math.floor(seconds / 86400), h = Math.floor((seconds % 86400) / 3600), m = Math.floor((seconds % 3600) / 60);
  if (d) return `${d} d ${h} h`;
  if (h) return `${h} h ${m} min`;
  return m ? `${m} min` : `${Math.round(seconds)} s`;
}
const percent = (bps: number | null | undefined) => bps == null ? 'Unavailable' : `${bps / 100}%`;

export function Kpis({client, identityKey}: {client: Transport; identityKey: string}) {
  useLanguage();
  return <KpiBody key={identityKey} client={client} identityKey={identityKey} />;
}
function KpiBody({client, identityKey}: {client: Transport; identityKey: string}) {
  useLanguage();
  const [start, setStart] = React.useState(''); const [end, setEnd] = React.useState(''); const [query, setQuery] = React.useState('');
  const [error, setError] = React.useState<unknown>();
  const data = useRemote<KpiResult>(client, `kpis?${query}`, identityKey, !!query);
  return <section>
    <PageHeader title={tr("Process KPIs")} subtitle={tr("Measured from the recorded audit history. Missing events are never counted as improvement.")} />
    <Notice />
    <Panel title={tr("Choose a window")}>
      <form onSubmit={e => {
        e.preventDefault(); setError(undefined);
        const from = new Date(start), through = new Date(end);
        if (!Number.isFinite(from.getTime()) || !Number.isFinite(through.getTime()) || from > through || through > new Date()) {
          setQuery(''); setError({status: 400}); return;
        }
        setQuery(new URLSearchParams({window_start: from.toISOString(), window_end: through.toISOString()}).toString());}}>
        <div className="two-col">
          <label>{tr("From  ")}<input type="datetime-local" required value={start} onChange={e => setStart(e.target.value)} /></label>
          <label>{tr("Through  ")}<input type="datetime-local" required value={end} onChange={e => setEnd(e.target.value)} /></label>
        </div>
        <button className="primary">{tr("Measure selected window")}</button></form>
    </Panel>
    {!!error && <ErrorBox error={error} />}
    {query && !data.error && !data.data && <Loading />}
    {query && !!data.error && <ErrorBox error={data.error} />}
    {query && data.data && <div className="stack stack--lg" style={{marginTop: 24}}>
      <div className="stat-grid">
        <StatCard label={tr("Accepted records measured")} value={data.data.submission_to_acceptance.sample_count} tone="info" />
        <StatCard label={tr("Median time to acceptance")} value={duration(data.data.submission_to_acceptance.median_seconds)} hint={`90th percentile: ${duration(data.data.submission_to_acceptance.p90_seconds)}`} tone="info" />
        <StatCard label={tr("Correction cycles per record")} value={data.data.correction_cycles.mean_per_accepted_record ?? 'Unavailable'} tone="warning" />
        <StatCard label={tr("Renewed on time")} value={percent(data.data.renewed_on_time.percentage_bps)} tone="success" />
        <StatCard label={tr("Independently confirmed")} value={percent(data.data.confirmed_share.percentage_bps)}
          hint={`Unknown histories: ${data.data.confirmed_share.unknown_count ?? 'Unavailable'}`} tone="success" />
        <StatCard label={tr("Incomplete histories")} value={data.data.data_quality?.incomplete_process_histories ?? 'Unavailable'} tone="neutral" />
      </div>
      <Panel title={tr("Limitations")}><ul aria-label={tr("KPI limitations")}>{data.data.limitations?.map(text => <li key={text}>{tr(text)}</li>)}</ul></Panel>
    </div>}
  </section>;
}
