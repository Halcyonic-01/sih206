import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ApiError, get, onUnauthorized, post, type Role } from '@/api/client'
import type { CurrentUser, MfaChallenge } from './types'

type Status = 'loading' | 'authenticated' | 'anonymous' | 'error'

interface AuthContextValue {
  user: CurrentUser | null
  status: Status
  signedOut: boolean
  login: (username: string, password: string) => Promise<CurrentUser | MfaChallenge>
  /** Second step of sign-in for an account with an authenticator app. */
  verifyMfa: (code: string) => Promise<CurrentUser>
  logout: () => Promise<void>
  hasRole: (...roles: Role[]) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)
export const ME_KEY = ['auth', 'me'] as const

/** Drops every cached query except the current user, so one person's data is never shown to the next. */
function dropPrivateData(client: QueryClient, user: CurrentUser | null) {
  client.removeQueries({ predicate: (query) => query.queryKey[0] !== ME_KEY[0] })
  client.setQueryData(ME_KEY, user)
}

async function fetchMe(): Promise<CurrentUser | null> {
  try {
    return await get<CurrentUser>('/auth/me/')
  } catch (error) {
    if (error instanceof ApiError && error.isUnauthorized) return null
    throw error
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient()
  const [signedOut, setSignedOut] = useState(false)
  const me = useQuery({ queryKey: ME_KEY, queryFn: fetchMe, staleTime: 60_000, retry: false })

  // Any 401 from any request ends the local session and drops cached private data.
  useEffect(() => onUnauthorized(() => dropPrivateData(client, null)), [client])

  const login = useCallback(async (username: string, password: string) => {
    const result = await post<CurrentUser | MfaChallenge>('/auth/login/', { username, password })
    if ('mfa_required' in result) return result
    setSignedOut(false)
    dropPrivateData(client, result)
    return result
  }, [client])

  const verifyMfa = useCallback(async (code: string) => {
    const user = await post<CurrentUser>('/auth/mfa/verify/', { code })
    setSignedOut(false)
    dropPrivateData(client, user)
    return user
  }, [client])

  const logout = useCallback(async () => {
    // Mark intent before the request: a 401 can also end the local session.
    setSignedOut(true)
    try {
      await post('/auth/logout/')
    } finally {
      // The guard may render before AppShell navigates away. Do not remember the old
      // user's page as a login destination after an intentional sign-out.
      dropPrivateData(client, null)
    }
  }, [client])

  const user = me.data ?? null
  const status: Status = me.isPending ? 'loading' : me.isError ? 'error' : user ? 'authenticated' : 'anonymous'
  const value = useMemo<AuthContextValue>(() => ({
    user, status, signedOut, login, verifyMfa, logout,
    hasRole: (...roles) => !!user?.role && roles.includes(user.role),
  }), [user, status, signedOut, login, verifyMfa, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
