import { App as AntApp, ConfigProvider, Spin } from 'antd'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense, useState, type ReactNode } from 'react'
import enGB from 'antd/locale/en_GB';
import hiIN from 'antd/locale/hi_IN';
import { useLanguage } from '@/i18n';
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { AuthProvider } from '@/auth/AuthProvider'
import { RequireRole } from '@/auth/RequireRole'
import { AppShell } from '@/layout/AppShell'
import { appRoutes, publicRoutes } from '@/routes/registry'
import { theme } from '@/theme'

const LoginPage = lazy(() => import('@/pages/LoginPage'))
const HomePage = lazy(() => import('@/pages/HomePage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      // Client errors (401/403/404/409) will not change on retry; only retry outages.
      retry: (count, error) => !(error instanceof ApiError && error.status > 0 && error.status < 500) && count < 2,
    },
  },
})

const wrap = (node: ReactNode) => <Suspense fallback={<Spin fullscreen />}>{node}</Suspense>

export function buildRouter() {
  const claimsHome = appRoutes.some((route) => route.path === '/')
  return createBrowserRouter([
    { path: '/login', element: wrap(<LoginPage />) },
    ...publicRoutes.map((route) => ({ path: route.path, element: wrap(route.element) })),
    {
      element: <RequireRole><AppShell /></RequireRole>,
      children: [
        ...(claimsHome ? [] : [{ path: '/', element: <HomePage /> }]),
        ...appRoutes.map((route) => ({
          path: route.path,
          element: <RequireRole roles={route.roles}>{route.element}</RequireRole>,
        })),
        { path: '*', element: <NotFoundPage /> },
      ],
    },
  ])
}

export default function App() {
  const language = useLanguage();
  // Language changes must not replace the router or discard an unsaved form.
  const [router] = useState(buildRouter);
  return (
    <ConfigProvider theme={theme} locale={language === 'hi' ? hiIN : enGB}>
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <RouterProvider router={router} />
          </AuthProvider>
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>
  )
}
