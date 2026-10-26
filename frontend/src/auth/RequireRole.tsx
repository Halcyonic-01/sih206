import { t as tr, useLanguage } from '@/i18n';
import { Spin } from 'antd'
import type { ReactNode } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import type { Role } from '@/api/client'
import { ErrorState } from '@/components/states'
import { useAuth } from './AuthProvider'

/**
 * Gate for routes. With no `roles` it only requires a signed-in user with a portal role.
 * The server still enforces every rule; this just keeps people off screens that would only say 403.
 */
export function RequireRole({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  useLanguage();
  const { status, user, signedOut } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <Spin fullscreen tip={tr("Loading…")} />
  if (status === 'error') {
    return <ErrorState title={tr("Cannot reach the server")} detail={tr("Check the connection and reload the page.")} />
  }
  if (status === 'anonymous' || !user) {
    // The route change is a low-priority React transition; on a busy device it can take a moment. Say what is
    // happening (and offer the link) instead of showing a blank screen while it lands.
    const from = signedOut ? null : { from: location.pathname + location.search }
    return <>
      <Navigate to="/login" replace state={from} />
      <p role="status" className="session-ended">
        {tr("Your session has ended. Opening the sign-in page… ")}<Link to="/login" replace state={from}>{tr("Sign in")}</Link>
      </p>
    </>
  }
  if (!user.role) {
    return <ErrorState status={403} title={tr("No portal role assigned")}
                       detail={tr("Your account is signed in but has no portal role. Ask the portal administrator.")} />
  }
  if (roles && !roles.includes(user.role)) {
    return <ErrorState status={403} title={tr("Not available for your role")}
                       detail={tr("This screen is for a different role. Use the menu to open one of yours.")} />
  }
  return <>{children}</>
}
