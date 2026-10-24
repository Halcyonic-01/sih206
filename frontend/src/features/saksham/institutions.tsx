import * as React from 'react';
import {api, Approval, Institution, Obligation, ObligationDetail, Page, Transport, money} from './client';
import {ErrorBox, Loading, Notice, useRemote} from './shared';

export function InstitutionList({client, identityKey, onSelect}: {client: Transport; identityKey: string; onSelect: (id:number)=>void}) {
  const [q, setQ] = React.useState('');
  const [page, setPage] = React.useState(1);
  const remote = useRemote<Page<Institution>>(client, `institutions?q=${encodeURIComponent(q)}&page=${page}`, identityKey);
  return <section><h1>Institutions</h1><Notice/><label>Search institutions <input value={q} maxLength={100}
    onChange={e=>{setQ(e.target.value); setPage(1);}}/></label>
    {remote.error ? <ErrorBox error={remote.error}/> : !remote.data ? <Loading/> : <>
      {!remote.data.results.length ? <p>No visible institutions.</p> : <ul>{remote.data.results.map(i =>
        <li key={i.id}><button onClick={()=>onSelect(i.id)}>{i.name}</button> · {i.code}</li>)}</ul>}
      <button disabled={page===1} onClick={()=>setPage(page-1)}>Previous page</button>
      <button disabled={page*25 >= (remote.data.count??0)} onClick={()=>setPage(page+1)}>Next page</button></>}
    <button onClick={remote.reload}>Refresh</button></section>;
}

export function InstitutionDetail({client, identityKey, institutionId}: {client: Transport; identityKey:string; institutionId:number}) {
  return <InstitutionDetailBody key={`${identityKey}:${institutionId}`} client={client} identityKey={identityKey} institutionId={institutionId}/>;
}
function InstitutionDetailBody({client, identityKey, institutionId}: {client: Transport; identityKey:string; institutionId:number}) {
  const base = `institutions/${institutionId}`;
  const [programmePage,setProgrammePage]=React.useState(1);
  const [obligationPage,setObligationPage]=React.useState(1);
  const detail = useRemote<Institution>(client, base, identityKey);
  const programmes = useRemote<Page<Approval>>(client, `${base}/programme-approvals?page=${programmePage}`, identityKey);
  const obligations = useRemote<Page<Obligation>>(client, `${base}/obligations?page=${obligationPage}`, identityKey);
  // Gate all child rendering on successful parent scope resolution.
  if (detail.error) return <ErrorBox error={detail.error}/>;
  if (!detail.data) return <Loading/>;
  return <section key={`${identityKey}:${institutionId}`}><h1>{detail.data.name}</h1><Notice/>
    <p>{detail.data.profile ? `${detail.data.profile.aicte_id} · ${detail.data.profile.institution_type} · ${detail.data.profile.region}` : 'Institution profile unavailable.'}</p>
    <h2>Programme approvals</h2>{programmes.error ? <ErrorBox error={programmes.error}/> : !programmes.data ? <Loading/> :
      <ul>{programmes.data.results.map(p=><li key={p.id}>{p.programme} · {p.level} · {p.loa_ref} · {p.approved_on}</li>)}</ul>}
    <h2>Obligations</h2>{obligations.error ? <ErrorBox error={obligations.error}/> : !obligations.data ? <Loading/> :
      obligations.data.results.length ? obligations.data.results.map(o=><ObligationCard key={o.id} client={client} identityKey={identityKey} obligationId={o.id}/>) : <p>No obligations recorded.</p>}
    <nav aria-label="Programme pages"><button disabled={programmePage===1} onClick={()=>setProgrammePage(programmePage-1)}>Previous programmes</button>
      <button disabled={programmePage*25>=(programmes.data?.count??0)} onClick={()=>setProgrammePage(programmePage+1)}>Next programmes</button></nav>
    <nav aria-label="Obligation pages"><button disabled={obligationPage===1} onClick={()=>setObligationPage(obligationPage-1)}>Previous obligations</button>
      <button disabled={obligationPage*25>=(obligations.data?.count??0)} onClick={()=>setObligationPage(obligationPage+1)}>Next obligations</button></nav>
  </section>;
}

export function ObligationCard({client, identityKey, obligationId}: {client: Transport; identityKey:string; obligationId:number}) {
  const remote = useRemote<ObligationDetail>(client, `obligations/${obligationId}`, identityKey);
  if (remote.error) return <ErrorBox error={remote.error}/>;
  if (!remote.data) return <Loading/>;
  const item = remote.data, coverage = item.assessment.coverage;
  return <article><h3>Obligation {item.id}</h3><p>Recorded status: {item.status} · Basis: {item.basis}</p>
    <dl><dt>Required</dt><dd>{money(item.required_paise)}</dd><dt>Held</dt><dd>{money(coverage?.held_paise)}</dd>
      <dt>Shortfall</dt><dd>{money(coverage?.shortfall_paise)}</dd></dl>
    <table><caption>Coverage against the obligation term</caption><thead><tr><th>Term start</th><th>Term end</th><th>Continuous coverage through</th></tr></thead>
      <tbody><tr><td>{item.term_start??'Unavailable'}</td><td>{item.term_end??'Unavailable'}</td><td>{coverage?.coverage_end??'Unavailable'}</td></tr></tbody></table>
    <p>Assessment date: {item.assessment.as_of}. {item.assessment.status === 'UNAVAILABLE' ? 'Coverage unavailable; source integration required.' : 'Draft assessment for human review.'}</p>
    <ul>{item.assessment.findings?.map(f=><li key={f.code}>{f.explanation}</li>)}</ul>
    <p>Proof receipt assessment: {item.assessment.proof_assessment??'Unavailable'}.</p>
    <table><caption>Scoped holding timeline</caption><thead><tr><th>Holding</th><th>Issue date</th><th>Maturity</th><th>Amount</th><th>Review state</th></tr></thead>
      <tbody>{item.assessment.holdings?.map(h=><tr key={h.id}><td>{h.id}</td><td>{h.issue_date}</td><td>{h.maturity_date}</td><td>{money(h.amount_paise)}</td><td>{h.status}</td></tr>)}</tbody></table>
    {item.assessment.holdings==null&&<p>Holding timeline unavailable.</p>}
    <h4>Suggested follow-up</h4>{item.assessment.open_actions==null?<p>Follow-up assessment unavailable.</p>:<ul>{item.assessment.open_actions.map((a,i)=><li key={i}>{a.description} · {a.responsible_party}. Suggested only; no task assigned or notification delivered.</li>)}</ul>}
  </article>;
}

export function Calculator({client, identityKey, institutionId}: {client:Transport; identityKey:string; institutionId:number}) {
  return <CalculatorBody key={`${identityKey}:${institutionId}`} client={client} identityKey={identityKey} institutionId={institutionId}/>;
}
function CalculatorBody({client, identityKey, institutionId}: {client:Transport; identityKey:string; institutionId:number}) {
  const rules = useRemote<Page<{id:number;code:string;version:number}>>(client,'rules',identityKey);
  const [rule, setRule] = React.useState('');
  const [rows, setRows] = React.useState([{programme:'MANAGEMENT',level:'PG',land_tenure:'OWNED',building_tenure:'OWNED'}]);
  const [result, setResult] = React.useState<{required_paise:number;source_clause:string;rule_code:string;rule_version:number;as_of:string}|null>(null);
  const [error, setError] = React.useState<unknown>();
  const [busy, setBusy] = React.useState(false);
  const generation = React.useRef(0);
  function invalidate(){generation.current++;setResult(null);setError(undefined);}
  function update(index:number,field:string,value:string){invalidate();setRows(rows.map((r,i)=>i===index?{...r,[field]:value}:r));}
  React.useEffect(()=>()=>{generation.current++;},[]);
  async function calculate(e: React.FormEvent) {
    e.preventDefault(); const current = ++generation.current; setBusy(true); setError(undefined);
    try {const r = await client.post<NonNullable<typeof result>>(api('calculator'), {institution_id:institutionId,rule_set_id:Number(rule),approvals:rows});
      if(current===generation.current) setResult(r);}
    catch(error){if(current===generation.current) setError(error);} finally{setBusy(false);}
  }
  return <section><h1>Requirement calculator</h1><Notice/><p>Preview only; this does not save an obligation. Select each applicable programme and level once.</p>
    {!!rules.error&&<ErrorBox error={rules.error}/>}<form onSubmit={calculate}><fieldset disabled={busy}><legend>Hypothetical programmes</legend>
      <label>Rule version <select required value={rule} onChange={e=>{invalidate();setRule(e.target.value);}}><option value="">Select explicit rule</option>
        {rules.data?.results.map(r=><option key={r.id} value={r.id}>{r.code} v{r.version}</option>)}</select></label>
      {rows.map((row,index)=><fieldset key={index}><legend>Programme {index+1}</legend>
        <label>Programme code <input required value={row.programme} onChange={e=>update(index,'programme',e.target.value)}/></label>
        <label>Level <select value={row.level} onChange={e=>update(index,'level',e.target.value)}>{['DIPLOMA','UG','PG'].map(x=><option key={x}>{x}</option>)}</select></label>
        <label>Land tenure <select value={row.land_tenure} onChange={e=>update(index,'land_tenure',e.target.value)}>{['OWNED','LEASED'].map(x=><option key={x}>{x}</option>)}</select></label>
        <label>Building tenure <select value={row.building_tenure} onChange={e=>update(index,'building_tenure',e.target.value)}>{['OWNED','LEASED'].map(x=><option key={x}>{x}</option>)}</select></label>
        <button type="button" disabled={rows.length===1} onClick={()=>{invalidate();setRows(rows.filter((_,i)=>i!==index));}}>Remove programme {index+1}</button>
      </fieldset>)}
      <button type="button" disabled={rows.length>=100} onClick={()=>{invalidate();setRows([...rows,{programme:'',level:'UG',land_tenure:'OWNED',building_tenure:'OWNED'}]);}}>Add programme</button>
      <button disabled={!rule}>Calculate preview</button></fieldset></form>{!!error&&<ErrorBox error={error}/>}<p aria-live="polite">{money(result?.required_paise)}</p>
      {result&&<p>Assessed {result.as_of} using {result.rule_code} v{result.rule_version}, clause {result.source_clause}. Draft human-review context only.</p>}
  </section>;
}
