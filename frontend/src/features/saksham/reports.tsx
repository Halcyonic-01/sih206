import * as React from 'react';
import {api, Transport} from './client';
import {ErrorBox, Notice, useRemote} from './shared';

export function Reports({client, identityKey}: {client:Transport; identityKey:string}) {
  return <ReportsBody key={identityKey} client={client}/>;
}
function ReportsBody({client}: {client:Transport}) {
  const [kind, setKind] = React.useState('upcoming_maturities');
  const [error, setError] = React.useState<unknown>();
  const [busy, setBusy] = React.useState(false);
  return <section><h1>Reports</h1><Notice/><p>Scoped current records. Unavailable verification, typed-document and intervention adapters are listed in each workbook.</p>
    <label>Report <select value={kind} onChange={e=>setKind(e.target.value)}>{[
      ['pending_verifications','Pending officer review (verification state unavailable)'],['upcoming_maturities','Upcoming maturities'],
      ['missing_documents','Missing FDR supporting documents'],['intervention','Known intervention items'],['released_register','Released register']
    ].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
    <button disabled={busy} onClick={async()=>{setBusy(true);setError(undefined);try{await client.download(api(`reports/${kind}?download=xlsx`));}catch(e){setError(e);}finally{setBusy(false);}}}>Download XLSX</button>
    {!!error&&<ErrorBox error={error}/>}</section>;
}
interface Preview {preview_id:number|null;version?:number;status:string;valid_count:number;row_count:number|null;
  errors:{row:number|null;field:string;code:string}[];valid_rows:{row:number;values:Record<string,string>}[]}
export function InstitutionImport({client, identityKey}: {client:Transport; identityKey:string}) {
  return <ImportBody key={identityKey} client={client}/>;
}
function ImportBody({client}: {client:Transport}) {
  const [file,setFile]=React.useState<File>();
  const [preview,setPreview]=React.useState<Preview>();
  const [reason,setReason]=React.useState('');
  const [done,setDone]=React.useState(false);
  const [busy,setBusy]=React.useState(false);
  const [error,setError]=React.useState<unknown>();
  async function inspect(e:React.FormEvent){e.preventDefault();if(!file)return;setBusy(true);setError(undefined);setDone(false);
    try{const data=new FormData();data.set('file',file);setPreview(await client.post<Preview>(api('imports/institutions/preview'),data));}
    catch(e){setError(e);setPreview(undefined);}finally{setBusy(false);}}
  async function commit(){if(!preview?.preview_id||!reason.trim())return;setBusy(true);setError(undefined);
    try{await client.post(api(`imports/institutions/${preview.preview_id}/commit`),{version:preview.version,reason});setDone(true);setPreview(undefined);}
    catch(e){setError(e);setPreview(undefined);}finally{setBusy(false);}}
  return <section><h1>Import synthetic institutions</h1><Notice/><p>Officer-only. Preview first; the complete file must be valid. Existing institutions are never overwritten.</p>
    <form onSubmit={inspect}><fieldset disabled={busy}><legend>CSV preview</legend><label>SIMULATED CSV (up to 1 MiB) <input type="file" accept=".csv,text/csv" required
      onChange={e=>{setFile(e.target.files?.[0]);setPreview(undefined);setDone(false);setError(undefined);}}/></label><button>Preview</button></fieldset></form>
    {!!error&&<ErrorBox error={error}/>}<div aria-live="polite">{done&&<p>Import committed. New institution identities were created.</p>}</div>
    {preview&&<section><h2>Preview: {preview.status}</h2><p>{preview.valid_count} valid rows of {preview.row_count??'unknown'}.</p>
      <ul>{preview.errors.map((e,i)=><li key={i}>Row {e.row??'file'}, {e.field}: {e.code}</li>)}</ul>
      <table><caption>Candidate institutions</caption><thead><tr><th>Row</th><th>Code</th><th>Name</th></tr></thead><tbody>{preview.valid_rows.map(r=><tr key={r.row}><td>{r.row}</td><td>{r.values.institution_code}</td><td>{r.values.institution_name}</td></tr>)}</tbody></table>
      <label>Import reason <textarea maxLength={2000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
      <button disabled={busy||preview.status!=='VALID'||!preview.preview_id||!reason.trim()} onClick={commit}>Confirm complete-file import</button></section>}
  </section>;
}
interface KpiResult {submission_to_acceptance:{sample_count:number;median_seconds:string|null;p90_seconds:string|null};
  correction_cycles:{mean_per_accepted_record:string|null};confirmed_share:{percentage_bps:number|null};
  renewed_on_time:{percentage_bps:number|null}}
export function Kpis({client, identityKey}: {client:Transport; identityKey:string}) {
  return <KpiBody key={identityKey} client={client} identityKey={identityKey}/>;
}
function KpiBody({client,identityKey}: {client:Transport;identityKey:string}) {
  const [start,setStart]=React.useState('');const [end,setEnd]=React.useState('');const [query,setQuery]=React.useState('');
  const data=useRemote<KpiResult>(client,`kpis?${query}`,identityKey,!!query);
  return <section><h1>Process KPIs</h1><Notice/><p>Measured from visible recorded audit history. No independent confirmation or improvement is inferred from missing events.</p>
    <form onSubmit={e=>{e.preventDefault();setQuery(new URLSearchParams({window_start:new Date(start).toISOString(),window_end:new Date(end).toISOString()}).toString());}}>
      <label>From <input type="datetime-local" required value={start} onChange={e=>setStart(e.target.value)}/></label>
      <label>Through <input type="datetime-local" required value={end} onChange={e=>setEnd(e.target.value)}/></label><button>Measure selected window</button></form>
    {query&&!!data.error&&<ErrorBox error={data.error}/>} {query&&data.data&&<dl>
      <dt>Accepted samples</dt><dd>{data.data.submission_to_acceptance.sample_count}</dd>
      <dt>Median submission-to-acceptance seconds</dt><dd>{data.data.submission_to_acceptance.median_seconds??'Unavailable'}</dd>
      <dt>p90 seconds</dt><dd>{data.data.submission_to_acceptance.p90_seconds??'Unavailable'}</dd>
      <dt>Mean correction cycles</dt><dd>{data.data.correction_cycles.mean_per_accepted_record??'Unavailable'}</dd>
      <dt>Renewed on time</dt><dd>{data.data.renewed_on_time.percentage_bps==null?'Unavailable':`${data.data.renewed_on_time.percentage_bps/100}%`}</dd>
      <dt>Independently confirmed share</dt><dd>{data.data.confirmed_share.percentage_bps==null?'Unavailable':`${data.data.confirmed_share.percentage_bps/100}%`}</dd></dl>}
  </section>;
}
