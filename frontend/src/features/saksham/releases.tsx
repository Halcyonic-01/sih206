import * as React from 'react';
import {api, Case, Page, PublicRecord, publicRecord, Transport, money, paise, Failure} from './client';
import {ErrorBox, Loading, Notice, Readiness, useRemote} from './shared';

export interface ReleaseInputs {
  instrumentId:number; obligationId:number; instrumentVersion:number;
  // TODO(Y2/Y3/S5-D04/K4): supplied from authorized server capabilities, never fixtures.
  canRequest:boolean;
  questionnaire?:{version:string;questions:{id:string;label:string}[]};
  documentPath?:string; onPathChange?:(path:string)=>void;
  documentsReady:boolean; documents:React.ReactNode;
}
export function ReleaseWizard({client,identityKey,inputs,onCreated}:{client:Transport;identityKey:string;inputs:ReleaseInputs;onCreated:(id:number)=>void}){
  return <WizardBody key={`${identityKey}:${inputs.instrumentId}:${inputs.instrumentVersion}:${inputs.questionnaire?.version??''}`} client={client} inputs={inputs} onCreated={onCreated}/>;
}
function WizardBody({client,inputs,onCreated}:{client:Transport;inputs:ReleaseInputs;onCreated:(id:number)=>void}){
  const [step,setStep]=React.useState(0);const [path,setPath]=React.useState('TERM_COMPLETE');
  const [answers,setAnswers]=React.useState<Record<string,boolean|null>>({});const [reason,setReason]=React.useState('');
  const [busy,setBusy]=React.useState(false);const [error,setError]=React.useState<unknown>();
  const title=React.useRef<HTMLHeadingElement>(null);
  React.useEffect(()=>{title.current?.focus();},[step]);
  const questionnaire=inputs.questionnaire;
  const answered=!!questionnaire?.questions.length&&questionnaire.questions.every(q=>typeof answers[q.id]==='boolean');
  const documentsReady=inputs.documentsReady&&inputs.documentPath===path;
  const nextAllowed=step===0?!!reason.trim():step===1?answered:documentsReady;
  async function submit(){if(!inputs.canRequest||!answered||!documentsReady||!reason.trim())return;setBusy(true);setError(undefined);
    try{const result=await client.post<Case>(api('releases'),{instrument_id:inputs.instrumentId,obligation_id:inputs.obligationId,
      instrument_version:inputs.instrumentVersion,path,declarations:answers,reason,template_ref:questionnaire?.version});onCreated(result.id);}catch(e){setError(e);}finally{setBusy(false);}}
  return <section><h1>Request release</h1><Notice/><ol aria-label="Release request steps">{['Path','Declarations','Documents','Review'].map((s,i)=><li key={s} aria-current={i===step?'step':undefined}>{s}</li>)}</ol>
    <h2 ref={title} tabIndex={-1}>{['Select path','Record declarations','Review documents','Review and submit'][step]}</h2>
    {!!error&&<ErrorBox error={error}/>}<fieldset disabled={busy}><legend>Release request</legend>
    {step===0&&<><label>Path <select value={path} onChange={e=>{setPath(e.target.value);setAnswers({});inputs.onPathChange?.(e.target.value);}}>{[
      ['TERM_COMPLETE','Term complete'],['PROGRESSIVE_CLOSURE','Progressive closure'],['MERGER','Merger'],
      ['CONVERSION_TO_UNIVERSITY','Conversion to university'],['CLOSURE_BY_AICTE','Closure by AICTE']].map(([v,l])=><option key={v} value={v}>{l}</option>)}</select></label>
      <label>Reason <textarea required maxLength={2000} value={reason} onChange={e=>setReason(e.target.value)}/></label></>}
    {step===1&&(!questionnaire?<p role="alert">Declaration template unavailable. Obtain the approved Affidavit-6 questionnaire; no questions have been invented.</p>:<>
      <p>Questionnaire version: {questionnaire.version}</p>{questionnaire.questions.map(q=><label key={q.id}>{q.label}<select value={answers[q.id]==null?'':String(answers[q.id])}
      onChange={e=>setAnswers({...answers,[q.id]:e.target.value===''?null:e.target.value==='true'})}><option value="">Not answered</option><option value="true">Yes</option><option value="false">No</option></select></label>)}</>)}
    {step===2&&<><p>Path: {path.replaceAll('_',' ').toLowerCase()}. Required document and exception checks must come from the authorized source.</p>
      {inputs.documents??<p role="alert">Scoped document upload/viewing integration unavailable.</p>}
      {!documentsReady&&<p role="alert">Required document review is incomplete, stale for this path or unavailable.</p>}</>}
    {step===3&&<><p>Path: {path.replaceAll('_',' ').toLowerCase()}</p><p>Reason: {reason}</p><p>Submission requests human review. Clearances, penalties, approval, letters and completion remain separate.</p>
      {!inputs.canRequest&&<p role="alert">Submission permission or source context unavailable.</p>}
      <button disabled={!inputs.canRequest||!answered||!documentsReady} onClick={submit}>Submit release request</button></>}
    <button disabled={step===0} onClick={()=>setStep(step-1)}>Back</button>{step<3&&<button disabled={!nextAllowed} onClick={()=>setStep(step+1)}>Next</button>}
    </fieldset></section>;
}

export function ReleaseCase({client,identityKey,caseId}:{client:Transport;identityKey:string;caseId:number}){
  return <CaseBody key={`${identityKey}:${caseId}`} client={client} identityKey={identityKey} caseId={caseId}/>;
}
function CaseBody({client,identityKey,caseId}:{client:Transport;identityKey:string;caseId:number}){
  const remote=useRemote<Case>(client,`releases/${caseId}`,identityKey);
  const [busy,setBusy]=React.useState(false);const [error,setError]=React.useState<unknown>();
  const [reason,setReason]=React.useState('');const [file,setFile]=React.useState<File>();const [refund,setRefund]=React.useState('');
  const [penalty,setPenalty]=React.useState('premature_encashment');const [base,setBase]=React.useState('');
  async function mutate(action:string,extra:Record<string,unknown>={},multipart?:FormData){if(!remote.data||!reason.trim()||busy)return;
    setBusy(true);setError(undefined);const current=remote.data;
    try{const payload=multipart??{version:current.version,reason,
      ...(['approve','reject'].includes(action)?{instrument_version:current.instrument_version}:{}),...extra};
      await client.post(api(`releases/${caseId}/${action}`),payload);setReason('');setFile(undefined);}
    catch(e){setError(e);}finally{remote.reload();setBusy(false);}}
  if(remote.error)return <ErrorBox error={remote.error}/>;if(!remote.data)return <Loading/>;
  const item=remote.data;
  return <section><h1>Release case {item.id}</h1><Notice/><p>Saved status: {item.status}. {item.status==='APPROVED'?'Release authorized; completion pending.':''}</p>
    <p>Monitoring: {item.monitoring_active?'Active':'Ended by recorded completion'}</p><p role="status">Next action: {item.next_action}</p>
    <p>Responsible party: {item.responsible_party??'Unavailable'}</p><p>Application reason: {item.application_reason??'Unavailable'}</p>
    {item.decision_reason&&<p>Recorded decision reason: {item.decision_reason}</p>}
    <h2>Protected documents</h2>{item.documents?<ul>{item.documents.map(d=><li key={d.id}>{d.name} · {d.kind} · {d.page_count==null?'Page count unavailable':`${d.page_count} pages`}
      {/^\/(?!\/)/.test(d.download_path)&&<button disabled={busy} onClick={()=>client.download(d.download_path).catch(setError)}>Download {d.name}</button>}</li>)}</ul>:<p>Document metadata unavailable.</p>}
    <Readiness value={item.readiness}/>{!!error&&<ErrorBox error={error}/>}
    <h2>Clearances</h2><ul>{item.clearances.map(t=><li key={t.unit}>{t.unit}: {t.status} {t.reason}</li>)}</ul>
    <h2>Penalties</h2><ul>{item.penalties.map(p=><li key={p.id}>{p.kind.replaceAll('_',' ')}: {money(p.amount_paise)} · {p.status} · clause {p.clause}
      {item.actions.can_review_penalties&&p.status==='PROPOSED'&&<button disabled={busy||!reason.trim()} onClick={()=>mutate('penalties',{confirm_id:p.id})}>Confirm reviewed proposal</button>}</li>)}</ul>
    <p>Review complete: {item.penalty_review_complete?'Yes':'No'}. Confirmation does not prove payment or authorize deduction.</p>
    <fieldset disabled={busy}><legend>Human action and reason</legend><label>Reason / completion notes <textarea required maxLength={2000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
    {item.actions.can_review_penalties&&<><label>Penalty kind <select value={penalty} onChange={e=>setPenalty(e.target.value)}>{['premature_encashment','closure_lapsed','closure_six_years'].map(k=><option key={k} value={k}>{k.replaceAll('_',' ')}</option>)}</select></label>
      <label>Reviewed penalty base (INR) <input inputMode="decimal" value={base} onChange={e=>setBase(e.target.value)}/></label>
      <button disabled={!reason.trim()||!base} onClick={()=>{try{void mutate('penalties',{kind:penalty,base_paise:paise(base)});}catch(e){setError(e);}}}>Propose penalty for review</button>
      <button disabled={!reason.trim()} onClick={()=>mutate('penalties')}>Record complete penalty review</button></>}
    {item.actions.can_approve&&<button disabled={!reason.trim()} onClick={()=>mutate('approve')}>Record authority authorization</button>}
    {item.actions.can_reject&&<button disabled={!reason.trim()} onClick={()=>mutate('reject')}>Record authority rejection</button>}
    {item.actions.can_issue&&<button disabled={!reason.trim()} onClick={()=>mutate('issue')}>Generate unsigned demo letter</button>}
    <h2>Letter</h2>{item.letter?<><p>{item.letter.kind}: {item.letter.serial} · {item.letter.revoked?'Revoked':'Issued demo record'} · Unsigned</p>
      <button onClick={()=>client.download(api(`releases/${caseId}/letter`)).catch(setError)}>Download protected letter</button></>:<p>Not issued.</p>}
    {item.actions.can_revoke&&<button disabled={!reason.trim()} onClick={()=>mutate('revoke')}>Revoke demo letter</button>}
    <h2>Separate completion</h2>{item.actions.can_complete?<><label>New completion PDF <input type="file" accept="application/pdf,.pdf" onChange={e=>setFile(e.target.files?.[0])}/></label>
      {item.mode==='RTGS'&&<label>Recorded bank/PFMS refund reference <input maxLength={200} value={refund} onChange={e=>setRefund(e.target.value)}/></label>}
      <button disabled={!file||!reason.trim()||(item.mode==='RTGS'&&!refund.trim())} onClick={()=>{if(!file)return;const data=new FormData();
        data.set('version',String(item.version));data.set('instrument_version',String(item.instrument_version));data.set('notes',reason);data.set('refund_reference',refund);data.set('document',file);
        void mutate('complete',{},data);}}>Record evidence-backed completion</button></>:<p>Completion action unavailable for this saved state or source context.</p>}
    </fieldset>{item.completion_notes&&<p>Recorded completion notes: {item.completion_notes}</p>}
    <h2>Recorded case history</h2><ol>{item.history?.map((h,i)=><li key={i}>{h.action.replaceAll('_',' ').toLowerCase()} · {new Date(h.at).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})} IST · {h.reason}</li>)}</ol>
    {item.history_has_more&&<p>Latest 100 events shown; additional history exists.</p>}
    <button disabled={busy} onClick={remote.reload}>Reload saved case</button></section>;
}

interface Task {case_id:number;version:number;unit:string;status:string;can_decide:boolean;due_date:string|null}
export function ClearanceQueue({client,identityKey,onSelect}:{client:Transport;identityKey:string;onSelect:(id:number)=>void}){
  return <QueueBody key={identityKey} client={client} identityKey={identityKey} onSelect={onSelect}/>;
}
function QueueBody({client,identityKey,onSelect}:{client:Transport;identityKey:string;onSelect:(id:number)=>void}){
  const [page,setPage]=React.useState(1);
  const remote=useRemote<Page<Task>>(client,`clearance-tasks?page=${page}`,identityKey);
  const [reason,setReason]=React.useState('');const [evidence,setEvidence]=React.useState('');
  const [error,setError]=React.useState<unknown>();const [busy,setBusy]=React.useState(false);
  async function decide(task:Task,status:string){setBusy(true);setError(undefined);try{await client.post(api(`releases/${task.case_id}/clearances/${task.unit}`),
    {version:task.version,status,reason,evidence_ref:evidence});setReason('');setEvidence('');}catch(e){setError(e);}finally{remote.reload();setBusy(false);}}
  return <section><h1>Assigned clearance work</h1><Notice/>{!!remote.error&&<ErrorBox error={remote.error}/>} {!!error&&<ErrorBox error={error}/>}
    {!remote.error&&!remote.data&&<Loading/>}{remote.data?.results.length===0&&<p>No assigned clearance work. This does not mean all cases are cleared.</p>}
    <fieldset disabled={busy}><legend>Clearance reason and evidence</legend><label>Reason <textarea maxLength={2000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
      <label>Reviewed evidence reference <input maxLength={200} value={evidence} onChange={e=>setEvidence(e.target.value)}/></label>
      <ul>{remote.data?.results.map(t=><li key={`${t.case_id}:${t.unit}`}><button onClick={()=>onSelect(t.case_id)}>Case {t.case_id}</button> · {t.unit} · {t.status} · Due {t.due_date??'Unavailable'}
        {t.can_decide&&['CLEARED','OBJECTION','HOLD'].map(s=><button key={s} disabled={!reason.trim()||!evidence.trim()} onClick={()=>decide(t,s)}>{s.toLowerCase()}</button>)}</li>)}</ul></fieldset>
    <button disabled={page===1||busy} onClick={()=>setPage(page-1)}>Previous tasks</button>
    <button disabled={page*25>=(remote.data?.count??0)||busy} onClick={()=>setPage(page+1)}>Next tasks</button>
  </section>;
}

export function PublicVerification({client,token}:{client:Transport;token:string}){
  const remote=useRemote<unknown>(client,`public/verify/${encodeURIComponent(token)}`,token);
  if(remote.error){const status=(remote.error as Failure)?.status;return <section><h1>Verify demo letter</h1><Notice/>
    <p role="alert">{status===404||status===400?'Verification record unavailable.':'Verification service temporarily unavailable.'}</p><button onClick={remote.reload}>Retry</button></section>;}
  if(!remote.data)return <Loading/>;
  let record:PublicRecord;try{record=publicRecord(remote.data);}catch{return <p role="alert">Verification response unavailable.</p>;}
  return <section><h1>{record.status==='REVOKED'?'Revoked — do not rely on this letter':'Issued demo record found'}</h1><Notice/>
    <dl><dt>Serial</dt><dd>{record.serial}</dd><dt>Issue date</dt><dd>{record.issue_date}</dd><dt>Institution</dt><dd>{record.institution_name}</dd><dt>Kind</dt><dd>{record.kind}</dd></dl>
    <p>Record lookup only; no independent bank confirmation or digital signature.</p></section>;
}
