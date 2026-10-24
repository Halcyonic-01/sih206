import { Spin } from 'antd'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import type { Role } from '@/api/client'
import { ErrorState } from '@/components/states'
import { useAuth } from './AuthProvider'

/**
 * Gate for routes. With no `roles` it only requires a signed-in user with a portal role.
 * The server still enforces every rule; this just keeps people off screens that would only say 403.
 */
export function RequireRole({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { status, user } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <Spin fullscreen tip="Loading…" />
  if (status === 'error') {
    return <ErrorState title="Cannot reach the server" detail="Check the connection and reload the page." />
  }
  if (status === 'anonymous' || !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }
  if (!user.role) {
    return <ErrorState status={403} title="No portal role assigned"
                       detail="Your account is signed in but has no portal role. Ask the portal administrator." />
  }
  if (roles && !roles.includes(user.role)) {
    return <ErrorState status={403} title="Not available for your role"
                       detail="This screen is for a different role. Use the menu to open one of yours." />
  }
  return <>{children}</>
}
