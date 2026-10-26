import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { RecordForm } from '@/features/records/RecordForm';
import { NotificationItem } from '@/features/notifications/NotificationItem';
import { PageHeader } from '@/components/PageHeader';
import { LanguageToggle } from './LanguageToggle';
import { LANGUAGE_KEY, setLanguage, t } from './index';
import sourceKeys from './source-keys.json';
import dynamicKeys from './dynamic-keys.json';
import hi from './hi.json';
import help from './hi-help.json';
import domain from './hi-domain.json';
import dynamic from './hi-dynamic.json';

afterEach(() => {act(() => setLanguage('en')); localStorage.removeItem(LANGUAGE_KEY); vi.restoreAllMocks();});

describe('English / Hindi interface', () => {
  it('covers every localized source key and preserves interpolation data literally', () => {
    const catalog: Record<string,string> = {...hi,...help,...domain,...dynamic};
    for (const key of [...sourceKeys,...dynamicKeys]) expect(catalog[key], key).toMatch(/[\u0900-\u097f]/);
    setLanguage('hi');
    expect(t('Welcome, {name}', {name:'Dashboard <script>alert(1)</script>'})).toBe('स्वागत है, Dashboard <script>alert(1)</script>');
    expect(t('Unknown reference XYZ/123')).toBe('Unknown reference XYZ/123');
  });

  it('switches form labels without losing unsaved values, numeric strings or dates', async () => {
    render(<><LanguageToggle /><RecordForm api={{request: vi.fn(), document: vi.fn()}} onSaved={() => {}} onCancel={() => {}} /></>);
    fireEvent.change(screen.getByLabelText('Instrument reference'), {target:{value:'FDR/EN-2026'}});
    fireEvent.change(screen.getByLabelText('Issuing bank'), {target:{value:'Dashboard'}});
    fireEvent.change(screen.getByLabelText('Amount (INR)'), {target:{value:'500000.25'}});
    fireEvent.change(screen.getByLabelText('Issue / payment date'), {target:{value:'2026-10-27'}});
    await userEvent.setup().click(screen.getByRole('button', {name:/हिन्दी/}));
    expect(document.documentElement.lang).toBe('hi');
    expect(localStorage.getItem(LANGUAGE_KEY)).toBe('hi');
    expect(screen.getByLabelText('लिखत संदर्भ')).toHaveValue('FDR/EN-2026');
    expect(screen.getByLabelText('जारीकर्ता बैंक')).toHaveValue('Dashboard');
    expect(screen.getByLabelText('राशि (INR)')).toHaveValue('500000.25');
    expect(screen.getByLabelText('जारी / भुगतान तिथि')).toHaveValue('2026-10-27');
    await userEvent.setup().click(screen.getByRole('button', {name:/English/}));
    expect(screen.getByLabelText('Issuing bank')).toHaveValue('Dashboard');
  });

  it('translates system notification text without modifying its original or free-form content', () => {
    const item = {id:1,template_id:'instrument_submitted',subject:'New submission: R1',body:'Original R1',link:'/records/1',
      severity:'info' as const,created_at:'2026-10-27T00:00:00Z',read_at:null,is_read:false,
      translations:{hi:{subject:'नई जमा: R1',body:'समीक्षा करें R1'}}};
    render(<MemoryRouter><LanguageToggle /><NotificationItem item={item} onRead={() => {}} /></MemoryRouter>);
    act(() => setLanguage('hi'));
    expect(screen.getByText('नई जमा: R1')).toBeInTheDocument();
    expect(item.body).toBe('Original R1');
    act(() => setLanguage('en'));
    expect(screen.getByText('New submission: R1')).toBeInTheDocument();
  });

  it('does not translate a record title or breadcrumb which happens to equal a UI key', () => {
    render(<MemoryRouter><PageHeader title="Dashboard" /></MemoryRouter>);
    act(() => setLanguage('hi'));
    expect(screen.getByRole('heading', {name:'Dashboard'})).toBeInTheDocument();
    expect(screen.getByText('मुख्य पृष्ठ')).toBeInTheDocument();
  });

  it('works when local preference storage is blocked', () => {
    vi.spyOn(Storage.prototype,'setItem').mockImplementation(() => {throw new Error('blocked');});
    expect(() => setLanguage('hi')).not.toThrow();
    expect(t('Sign in')).toBe('साइन इन करें');
  });
});
