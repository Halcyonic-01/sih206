import { Suspense } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AuthProvider } from '@/auth/AuthProvider';
import { RequireRole } from '@/auth/RequireRole';
import { publicRoutes, routes } from './routes';

const fetchMock=vi.fn<typeof fetch>();
let role='officer';
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
function mount(path:string){
  const cache=new QueryClient({defaultOptions:{queries:{retry:false}}});
  return render(<QueryClientProvider client={cache}><AuthProvider><MemoryRouter initialEntries={[path]}>
    <Suspense fallback={<p>Loading route</p>}><Routes>{routes.map(route=><Route key={route.path} path={route.path}
      element={<RequireRole roles={route.roles}>{route.element}</RequireRole>}/>)}
      <Route path="/login" element={<h1>Sign in required</h1>}/></Routes></Suspense>
  </MemoryRouter></AuthProvider></QueryClientProvider>);
}
beforeEach(()=>{
  role='officer';vi.stubGlobal('fetch',fetchMock);document.cookie='csrftoken=p5-test; path=/';
  fetchMock.mockImplementation(async path=>{
    const url=String(path);
    if(url==='/api/auth/me/')return json({id:1,username:'synthetic',display_name:'Synthetic',role,institution:null,unit:null});
    if(url.startsWith('/api/reports/'))return json({rows:[],limitations:['Actual source limitation']});
    if(url==='/api/imports/institutions/preview')return json({preview_id:7,version:1,status:'VALID',valid_count:1,row_count:1,
      errors:[],valid_rows:[{row:2,values:{institution_code:'SYNTH',institution_name:'Synthetic college'}}]});
    if(url==='/api/imports/institutions/7/commit')return json({status:'COMMITTED'});
    if(url.startsWith('/api/kpis?'))return json({submission_to_acceptance:{sample_count:0,median_seconds:null,p90_seconds:null},
      correction_cycles:{mean_per_accepted_record:null},confirmed_share:{percentage_bps:null,unknown_count:1},
      renewed_on_time:{percentage_bps:null},data_quality:{incomplete_process_histories:1},limitations:['Unknown renewal eligibility']});
    return json({},404);
  });
});
afterEach(()=>{fetchMock.mockReset();vi.unstubAllGlobals();});

it('registers S4 and owned release screens through the shared route registry',()=>{
  expect(routes.filter(r=>['/reports','/kpis','/imports/institutions'].includes(r.path))).toHaveLength(3);
  expect(routes.some(r=>r.path==='/releases/request')).toBe(true);
  expect(routes.some(r=>r.path==='/releases/:caseId')).toBe(true);
  expect(routes.some(r=>r.path==='/clearance-tasks')).toBe(true);
  expect(publicRoutes.some(r=>r.path==='/verify/:token')).toBe(true);
});
it('loads scoped empty report and visible limitations through shared HTTP',async()=>{
  mount('/reports');
  expect(await screen.findByText('No matching items.')).toBeInTheDocument();
  expect(screen.getByText('Actual source limitation')).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Download XLSX'})).toBeEnabled();
  fireEvent.change(screen.getByLabelText('Report'),{target:{value:'missing_documents'}});
  await waitFor(()=>expect(fetchMock.mock.calls.some(([url])=>url==='/api/reports/missing_documents')).toBe(true));
});
it.each([403,409,503])('report %i shows focused error and disables download',async status=>{
  const source=fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((path,init)=>String(path).startsWith('/api/reports/')?
    Promise.resolve(json({detail:'Failed source',code:'test'},status)):source(path,init));
  mount('/reports');
  expect(await screen.findByRole('alert')).toHaveFocus();
  expect(screen.getByRole('button',{name:'Download XLSX'})).toBeDisabled();
});
it('institution cannot fetch or see the officer import form',async()=>{
  role='institution';mount('/imports/institutions');
  expect(await screen.findByText('Not available for your role')).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Preview'})).not.toBeInTheDocument();
  expect(fetchMock.mock.calls.some(([url])=>String(url).includes('/preview'))).toBe(false);
});
it('preview then explicit commit sends multipart and CSRF/version/reason',async()=>{
  mount('/imports/institutions');const user=userEvent.setup();
  const input=await screen.findByLabelText('SIMULATED CSV (up to 1 MiB)');
  await user.upload(input,new File(['SIMULATED fixture'], 'synthetic.csv',{type:'text/csv'}));
  expect((input as HTMLInputElement).files).toHaveLength(1);
  // Exercise the React submit boundary; native file-validity/click submission
  // is checked in the real Edge rehearsal (jsdom does not implement it fully).
  fireEvent.submit(input.closest('form')!);
  expect(await screen.findByText('Synthetic college')).toBeInTheDocument();
  const confirm=screen.getByRole('button',{name:'Confirm complete-file import'});
  expect(confirm).toBeDisabled();
  await user.type(screen.getByLabelText('Import reason'),'Reviewed synthetic rows');await user.click(confirm);
  expect(await screen.findByText('Import committed. New institution identities were created.')).toBeInTheDocument();
  const preview=fetchMock.mock.calls.find(([url])=>url==='/api/imports/institutions/preview')!;
  expect(preview[1]?.body).toBeInstanceOf(FormData);
  const commit=fetchMock.mock.calls.find(([url])=>url==='/api/imports/institutions/7/commit')!;
  expect(commit[1]?.body).toBe(JSON.stringify({version:1,reason:'Reviewed synthetic rows'}));
  expect((commit[1]?.headers as Record<string,string>)['X-CSRFToken']).toBe('p5-test');
});
it('stale import discards the consumed preview and requires another preview',async()=>{
  const source=fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((path,init)=>String(path).endsWith('/commit')?
    Promise.resolve(json({detail:'Stale',code:'conflict'},409)):source(path,init));
  mount('/imports/institutions');const user=userEvent.setup();
  await user.upload(await screen.findByLabelText('SIMULATED CSV (up to 1 MiB)'),new File(['x'],'synthetic.csv',{type:'text/csv'}));
  fireEvent.submit(screen.getByLabelText('SIMULATED CSV (up to 1 MiB)').closest('form')!);
  await user.type(await screen.findByLabelText('Import reason'),'Reviewed synthetic rows');
  await user.click(screen.getByRole('button',{name:'Confirm complete-file import'}));
  expect(await screen.findByRole('alert')).toHaveTextContent(/changed/i);
  expect(screen.queryByRole('button',{name:'Confirm complete-file import'})).not.toBeInTheDocument();
});
it('KPI selection shows unavailable histories and limitations without fake zeros',async()=>{
  mount('/kpis');
  fireEvent.change(await screen.findByLabelText('From'),{target:{value:'2026-01-01T00:00'}});
  fireEvent.change(screen.getByLabelText('Through'),{target:{value:'2026-01-02T00:00'}});
  fireEvent.click(screen.getByRole('button',{name:'Measure selected window'}));
  expect(await screen.findByText('Unknown renewal eligibility')).toBeInTheDocument();
  expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(1);
});
