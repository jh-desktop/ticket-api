import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

import { ApiError, get, post } from '../api/client'
import type { User } from '../api/types'

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<User>
  signup: (email: string, password: string) => Promise<User>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const Ctx = createContext<AuthState | null>(null)

/**
 * 로그인 상태. 토큰은 HttpOnly 쿠키라 JS 에서 볼 수 없다 → "로그인 됐나" 는 GET /auth/me 로 서버에 물어본다.
 * 앱이 처음 뜰 때 한 번, 로그인/로그아웃 뒤에 갱신한다.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    try {
      setUser(await get<User>('/auth/me'))
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setUser(null)
      else throw e
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const login = useCallback(async (email: string, password: string) => {
    const u = await post<User>('/auth/login', { email, password }) // 응답 본문엔 사용자만. 토큰은 Set-Cookie 로
    setUser(u)
    return u
  }, [])

  const signup = useCallback(async (email: string, password: string) => post<User>('/auth/signup', { email, password }), [])

  const logout = useCallback(async () => {
    await post<void>('/auth/logout')
    setUser(null)
  }, [])

  return <Ctx.Provider value={{ user, loading, login, signup, logout, refresh }}>{children}</Ctx.Provider>
}

export function useAuth(): AuthState {
  const v = useContext(Ctx)
  if (!v) throw new Error('AuthProvider missing')
  return v
}
