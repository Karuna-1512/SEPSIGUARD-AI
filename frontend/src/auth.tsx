import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, setCsrfToken } from './api'
import type { User } from './types'

type AuthValue = { user: User | null; loading: boolean; login: (email: string, password: string) => Promise<void>; logout: () => Promise<void> }
const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    api<{ user: User; csrf_token: string }>('/auth/me')
      .then(session => { setUser(session.user); setCsrfToken(session.csrf_token) })
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])
  const value = useMemo<AuthValue>(() => ({
    user, loading,
    login: async (email, password) => {
      const session = await api<{ user: User; csrf_token: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
      setUser(session.user); setCsrfToken(session.csrf_token)
    },
    logout: async () => { await api('/auth/logout', { method: 'POST' }); setUser(null); setCsrfToken(null) },
  }), [user, loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error('useAuth must be used inside AuthProvider'); return value }
