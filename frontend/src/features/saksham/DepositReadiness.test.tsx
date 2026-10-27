import {act} from 'react';
import {fireEvent, render, screen, waitFor} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {setLanguage} from '@/i18n';
import {DepositReadiness, safeReadinessLink, type ReadinessSummary} from './DepositReadiness';
import type {Transport} from './client';

const summary: ReadinessSummary = {institution_id: 1, completed: 4, applicable: 6, percent: 67,
  status: 'ACTION_OR_REVIEW_NEEDED', as_of: '2026-10-27', source_fingerprint: 'synthetic', obligations: [
    {obligation_id: 12, completed: 4, applicable: 6, percent: 67, mode: 'FDR', policy_source: 'Synthetic draft rule', items: [
      {id: 'affidavit_3', state: 'INCOMPLETE', reason: 'NOT_UPLOADED', helper: 'Upload required',
        deadline: {due_on: '2026-11-04', days_remaining: 8, state: 'UPCOMING'},
        targets: [{label: 'Upload Affidavit-3', href: '/records/5?readiness=upload&kind=AFFIDAVIT_3'}]},
      {id: 'bank_confirmation', state: 'SIMULATED', reason: 'SIMULATED_NOT_INDEPENDENTLY_CONFIRMED', deadline: null},
    ]},
  ]};
function client(value: unknown = summary): Transport {
  return {get: vi.fn(async () => value) as Transport['get'], post: vi.fn(), download: vi.fn()};
}
function view(source: Transport, identityKey = 'user1', focusObligationId?: number) {
  return <MemoryRouter><DepositReadiness client={source} identityKey={identityKey} institutionId={1}
    focusObligationId={focusObligationId} renderTarget={id => <p>Selected obligation {id}</p>} /></MemoryRouter>;
}
afterEach(() => act(() => setLanguage('en')));
describe('deposit readiness', () => {
  it('shows counts, accessible progress, recorded deadline and exact action link', async () => {
    render(view(client()));
    expect((await screen.findAllByText('4 of 6 applicable recorded steps complete (67%)')).length).toBe(2);
    expect(screen.getAllByRole('progressbar')[0]).toHaveAttribute('value', '4');
    expect(screen.getByText(/Due in 8 days/)).toBeInTheDocument();
    expect(screen.getByRole('link', {name: 'Upload Affidavit-3'})).toHaveAttribute('href', '/records/5?readiness=upload&kind=AFFIDAVIT_3');
    expect(screen.getByText('Simulated')).toBeInTheDocument();
    expect(screen.getByRole('note')).toHaveTextContent('not regulatory compliance');
  });
  it('does not invent 100 percent for empty institutions', async () => {
    render(view(client({...summary, completed: 0, applicable: 0, percent: null, obligations: []})));
    await screen.findByText('No obligations recorded.');
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(screen.getByText('No applicable steps to measure.')).toBeInTheDocument();
  });
  it('loads the selected obligation only after membership is confirmed', async () => {
    const {rerender} = render(view(client(), 'user1', 12));
    await screen.findByText('Selected obligation 12');
    rerender(view(client(), 'user1', 999));
    await screen.findByRole('alert');
    expect(screen.queryByText('Selected obligation 999')).not.toBeInTheDocument();
  });
  it('retries an outage and refreshes after an actual receipt action', async () => {
    const source = client();
    vi.mocked(source.get).mockRejectedValueOnce({status: 503}).mockResolvedValue(summary);
    render(view(source)); await screen.findByRole('alert');
    fireEvent.click(screen.getByRole('button', {name: 'Refresh readiness'}));
    await screen.findAllByText('4 of 6 applicable recorded steps complete (67%)');
    act(() => window.dispatchEvent(new Event('pramaan:readiness-changed')));
    await waitFor(() => expect(source.get).toHaveBeenCalledTimes(3));
  });
  it('rejects an unexpected institution and unsafe action paths', async () => {
    render(view(client({...summary, institution_id: 2})));
    await screen.findByRole('alert');
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    for (const href of ['https://example.invalid', '//example.invalid', 'javascript:alert(1)', '/api/delete', '/records/../evil'])
      expect(safeReadinessLink(href)).toBe(false);
  });
  it('switches labels to Hindi without changing record identifiers or target', async () => {
    render(view(client()));
    await screen.findByRole('link');
    act(() => setLanguage('hi'));
    expect(screen.getByRole('heading', {name: 'जमा तैयारी'})).toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute('href', '/records/5?readiness=upload&kind=AFFIDAVIT_3');
    expect(screen.getByText(/12 · FDR/)).toBeInTheDocument();
  });
});
