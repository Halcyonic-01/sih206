import * as React from 'react';
import {api, errorMessage, Transport} from './client';

export function useRemote<T>(client: Transport, path: string, identityKey: string, enabled = true) {
  const [revision, reload] = React.useReducer((n: number) => n + 1, 0);
  const [state, set] = React.useState<{key: string; data?: T; error?: unknown}>({key: ''});
  const key = `${identityKey}:${path}:${revision}`;
  React.useEffect(() => {
    if (!enabled) return;
    const abort = new AbortController();
    let active = true;
    set({key});
    client.get<T>(api(path), abort.signal).then(data => {if (active) set({key, data});},
      error => {if (active) set({key, error});});
    return () => {active = false; abort.abort();};
  }, [client, key, path, enabled]);
  // Never render previous identity/case while waiting for the effect to reset state.
  return {data: state.key === key ? state.data : undefined,
    error: state.key === key ? state.error : undefined, reload};
}
export function Notice() { return <p role="note">SIMULATED · Draft rules, not approved policy. Not independently bank-verified.</p>; }
export function ErrorBox({error}: {error: unknown}) {
  const ref = React.useRef<HTMLParagraphElement>(null);
  React.useEffect(()=>{ref.current?.focus();},[error]);
  return <p ref={ref} role="alert" tabIndex={-1}>{errorMessage(error)}</p>;
}
export function Loading() { return <p role="status">Loading…</p>; }
export function Readiness({value}: {value: {outcome: string; reason_codes?: string[]}|null}) {
  return <section aria-label="Readiness assessment"><h3>Readiness for human review</h3>
    <p>{value?.outcome === 'READY_FOR_AUTHORITY_REVIEW' ? 'Ready for human review; no approval recorded.' :
      value ? value.outcome.replaceAll('_',' ').toLowerCase() : 'Unavailable for this saved state.'}</p>
    <ul>{value?.reason_codes?.map(code => <li key={code}>{code.replaceAll('_',' ').toLowerCase()}</li>)}</ul></section>;
}
