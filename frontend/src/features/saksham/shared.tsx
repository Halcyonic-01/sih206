import { t as tr, useLanguage } from '@/i18n';
import * as React from 'react';
import { Skeleton } from 'antd';
import { api, errorMessage, Transport } from './client';

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

/** Marks screens that show simulated data or draft rules. Short, always visible. */
export function Notice() {
  useLanguage(); return <p role="note" className="notice">{tr("Simulated data · Draft rules, not approved policy")}</p>; }

export function ErrorBox({error}: {error: unknown}) {
  useLanguage();
  const ref = React.useRef<HTMLParagraphElement>(null);
  // Layout effect: focus moves in the same commit that shows the alert, so it is never visible unfocused.
  React.useLayoutEffect(() => {ref.current?.focus();}, [error]);
  return <p ref={ref} role="alert" tabIndex={-1}>{tr(errorMessage(error))}</p>;
}

export function Loading() {
  useLanguage(); return <div role="status" aria-live="polite" aria-label={tr("Loading")}><Skeleton active paragraph={{rows: 4}} /></div>; }

export function Readiness({value}: {value: {outcome: string; reason_codes?: string[]}|null}) {
  useLanguage();
  const ready = value?.outcome === 'READY_FOR_AUTHORITY_REVIEW';
  return <section aria-label={tr("Readiness assessment")}>
    <p>{ready ? tr("Ready for human review; no approval recorded.") :
      value ? tr(value.outcome.replaceAll('_',' ').toLowerCase()) : tr("Unavailable for this saved state.")}</p>
    {!!value?.reason_codes?.length && <ul>{value.reason_codes.map(code => <li key={code}>{code.replaceAll('_',' ').toLowerCase()}</li>)}</ul>}
  </section>;
}
