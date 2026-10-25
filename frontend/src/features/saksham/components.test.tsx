import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { Case, Transport } from './client';
import { InstitutionList } from './institutions';
import { PublicVerification, ReleaseCase, ReleaseWizard } from './releases';
import { Kpis } from './reports';

// Explicit test-only source ports; these tests do not claim HTTP/auth integration.
function transport(read: (path: string, signal?: AbortSignal) => Promise<unknown>,
  write: (path: string, body: unknown | FormData) => Promise<unknown> = async () => undefined): Transport {
  return {
    async get<T>(path: string, signal?: AbortSignal) { return await read(path, signal) as T; },
    async post<T>(path: string, body: unknown | FormData) { return await write(path, body) as T; },
    download: vi.fn(async () => undefined),
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}

const approvedCase: Case = {
  id: 1, version: 1, instrument_version: 5, status: 'APPROVED', path: 'TERM_COMPLETE', mode: 'FDR',
  monitoring_active: true, next_action: 'Separate evidence-backed completion', readiness: null,
  actions: {}, clearances: [], penalties: [], penalty_review_complete: true, letter: null,
};

describe('Saksham components in the shared frontend runner', () => {
  it('keeps approval monitored with completion pending', async () => {
    const client = transport(async () => approvedCase);
    render(<ReleaseCase client={client} identityKey="authority" caseId={1} />);
    expect(await screen.findByText(/Release authorized; completion pending/)).toBeInTheDocument();
    expect(screen.getByText('Monitoring').nextElementSibling).toHaveTextContent('Active');
    expect(screen.queryByRole('button', { name: 'Record evidence-backed completion' })).not.toBeInTheDocument();
  });

  it('does not grant authority actions from READY alone', async () => {
    const client = transport(async () => ({ ...approvedCase, status: 'PENDING',
      readiness: { outcome: 'READY_FOR_AUTHORITY_REVIEW' } }));
    render(<ReleaseCase client={client} identityKey="officer" caseId={1} />);
    expect(await screen.findByText(/no approval recorded/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Record authority authorization' })).not.toBeInTheDocument();
  });

  it('labels an AI release summary as advisory and sends the saved version', async () => {
    const write = vi.fn(async () => ({status: 'success', cached: false, label: 'AI-generated: verify before use',
      summary: 'Clearances remain open.', risk_flags: [{field: 'clearances[0].status', severity: 'warning', message: 'Open'}]}));
    const client = transport(async () => ({...approvedCase, actions: {can_ai_summary: true}}), write);
    render(<ReleaseCase client={client} identityKey="clearance" caseId={1} />);
    await userEvent.setup().click(await screen.findByRole('button', {name: 'Generate AI summary'}));
    expect(await screen.findByText('AI-generated: verify before use')).toBeInTheDocument();
    expect(write).toHaveBeenCalledWith('/api/releases/1/ai-summary', {version: 1});
  });

  it('keeps manual review available when the AI summary feature is off', async () => {
    const client = transport(async () => ({...approvedCase, ai_summary_enabled: false, actions: {can_ai_summary: true}}));
    render(<ReleaseCase client={client} identityKey="clearance" caseId={1} />);
    expect(await screen.findByText('AI summary is off. Continue manual release review.')).toBeInTheDocument();
    expect(screen.queryByRole('button', {name: 'Generate AI summary'})).not.toBeInTheDocument();
  });

  it('shows a failed service without synthetic fallback', async () => {
    const client = transport(async () => { throw { status: 503 }; });
    const { container } = render(<ReleaseCase client={client} identityKey="officer" caseId={1} />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Service unavailable');
    expect(container).not.toHaveTextContent(/SYNTH-|Saved status/);
  });

  it('discards an old identity response even when the source ignores abort', async () => {
    const first = deferred<unknown>();
    const second = deferred<unknown>();
    const read = vi.fn<(path: string, signal?: AbortSignal) => Promise<unknown>>()
      .mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const client = transport(read);
    const onSelect = vi.fn();
    const { rerender } = render(<InstitutionList client={client} identityKey="A" onSelect={onSelect} />);
    rerender(<InstitutionList client={client} identityKey="B" onSelect={onSelect} />);
    expect(read.mock.calls[0]?.[1]?.aborted).toBe(true);
    await act(async () => {
      second.resolve({ count: 1, results: [{ id: 2, name: 'Only B', code: 'B' }] });
    });
    expect(await screen.findByRole('button', { name: 'Only B' })).toBeInTheDocument();
    await act(async () => {
      first.resolve({ count: 1, results: [{ id: 1, name: 'Secret A', code: 'A' }] });
    });
    expect(screen.queryByText('Secret A')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Only B' })).toBeInTheDocument();
  });

  it('blocks the wizard without the canonical questionnaire', async () => {
    const write = vi.fn(async () => undefined);
    const client = transport(async () => undefined, write);
    render(<ReleaseWizard client={client} identityKey="institution"
      inputs={{ instrumentId: 1, obligationId: 1, instrumentVersion: 1,
        canRequest: true, documentsReady: true, documents: null }} onCreated={vi.fn()} />);
    const user = userEvent.setup();
    await user.type(screen.getByRole('textbox', { name: 'Reason' }), 'Synthetic request');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Declaration template unavailable');
    expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
    expect(write).not.toHaveBeenCalled();
  });

  it('ignores mutation projections and reloads saved state', async () => {
    let saved: Case = { ...approvedCase, status: 'PENDING', actions: { can_approve: true } };
    const read = vi.fn(async () => saved);
    const write = vi.fn(async () => {
      saved = approvedCase;
      return { case_status_after_action: 'COMPLETED', monitoring_after_action: false };
    });
    const client = transport(read, write);
    const { container } = render(<ReleaseCase client={client} identityKey="authority" caseId={1} />);
    const authorize = await screen.findByRole('button', { name: 'Record authority authorization' });
    expect(authorize).toBeDisabled();
    fireEvent.change(screen.getByRole('textbox', { name: 'Reason / completion notes' }),
      { target: { value: 'Independent review' } });
    await userEvent.setup().click(authorize);
    expect(await screen.findByText('Approved')).toBeInTheDocument();
    expect(screen.getByText('Monitoring').nextElementSibling).toHaveTextContent('Active');
    expect(container).not.toHaveTextContent('COMPLETED');
    expect(write).toHaveBeenCalledExactlyOnceWith('/api/releases/1/approve',
      { version: 1, instrument_version: 5, reason: 'Independent review' });
    expect(read).toHaveBeenCalledTimes(2);
  });

  it('renders revocation without private links or fields', async () => {
    const client = transport(async () => ({ serial: 'SYNTH-X', issue_date: '2026-10-24',
      institution_name: 'Synthetic', kind: 'NOC', status: 'REVOKED' }));
    const { container } = render(<PublicVerification client={client} token="synthetic-token" />);
    expect(await screen.findByRole('heading', { name: /Revoked/ })).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(container).not.toHaveTextContent(/monitoring|refund_reference/);
  });

  it.each([
    [404, 'Verification record unavailable.'],
    [503, 'Verification service temporarily unavailable.'],
  ])('distinguishes public lookup failure %i', async (status, message) => {
    const client = transport(async () => { throw { status }; });
    render(<PublicVerification client={client} token="synthetic-token" />);
    expect(await screen.findByRole('alert')).toHaveTextContent(message);
  });

  it('does not fetch KPIs before a cohort is specified', async () => {
    const read = vi.fn(async () => ({}));
    render(<Kpis client={transport(read)} identityKey="officer" />);
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Process KPIs' })).toBeInTheDocument());
    expect(read).not.toHaveBeenCalled();
  });
});
