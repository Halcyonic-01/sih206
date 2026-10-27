import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import WeeklyDigest from './WeeklyDigest'

const fetchMock=vi.fn<typeof fetch>()
const json=(body: unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}})
function mount(){render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><WeeklyDigest /></QueryClientProvider>)}
beforeEach(()=>{vi.stubGlobal('fetch',fetchMock);document.cookie='csrftoken=t; path=/'})
afterEach(()=>{fetchMock.mockReset();vi.unstubAllGlobals()})

it('shows server dispatch state, records saved preference and previews without sending',async()=>{
  let enabled=true,version=0
  fetchMock.mockImplementation(async(url,init)=>{
    if(String(url).includes('digest-preview'))return json({eligible:true,body:'Submissions pending review: 12'})
    if(init?.method==='PATCH'){const body=JSON.parse(String(init.body));expect(body.version).toBe(0);enabled=body.enabled;version=1}
    return json({enabled,version,dispatch_enabled:false})
  })
  mount()
  expect(await screen.findByText('Digest dispatch is disabled on this server')).toBeInTheDocument()
  const user=userEvent.setup()
  await user.click(screen.getByRole('checkbox',{name:'Receive weekly email digest'}))
  await waitFor(()=>expect(screen.getByRole('checkbox')).not.toBeChecked())
  await user.click(screen.getByRole('button',{name:'Preview my digest'}))
  expect(await screen.findByText('Submissions pending review: 12')).toBeInTheDocument()
  expect(fetchMock.mock.calls.every(([,init])=>!init?.method||init.method==='GET'||init.method==='PATCH')).toBe(true)
})

it('shows stale preference conflict and allows reload',async()=>{
  fetchMock.mockImplementation(async(_url,init)=>init?.method==='PATCH'
    ?json({detail:'Reload preference',code:'conflict'},409):json({enabled:true,version:1,dispatch_enabled:true}))
  mount();await userEvent.setup().click(await screen.findByRole('checkbox'))
  expect(await screen.findByText('This record changed')).toBeInTheDocument()
  expect(screen.getByRole('button',{name:'Reload'})).toBeInTheDocument()
})

it('shows source failure with retry rather than invented counts',async()=>{
  fetchMock.mockResolvedValue(json({detail:'Source unavailable',code:'unavailable'},503))
  mount();expect(await screen.findByText('Something went wrong')).toBeInTheDocument()
  expect(screen.getByRole('button',{name:'Try again'})).toBeInTheDocument()
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
})
