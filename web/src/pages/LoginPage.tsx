import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { ErrorLine, Explain } from '../components/Explain'
import { Term } from '../components/Term'
import { useAuth } from '../state/auth'

/** seed 스크립트가 만든 계정들 (uv run python -m app.scripts.seed). 비밀번호는 전부 password123 */
export const SEED_ACCOUNTS: Array<{ email: string; role: string; groups: string; note: string }> = [
  { email: 'admin@example.com', role: 'ADMIN', groups: '-', note: '전부 가능' },
  { email: 'writer@example.com', role: 'GROUP_WRITER', groups: 'backend', note: 'backend 그룹 티켓 승인' },
  { email: 'reader@example.com', role: 'GROUP_READER', groups: 'backend', note: 'backend 그룹 조회만' },
  { email: 'owner1@example.com', role: 'OWNER', groups: 'backend', note: '내 티켓만' },
  { email: 'owner2@example.com', role: 'OWNER', groups: 'mobile', note: '내 티켓만 (다른 그룹)' },
]
export const SEED_PASSWORD = 'password123'

export function LoginPage() {
  const { user, login, signup, logout } = useAuth()
  const nav = useNavigate()
  const [email, setEmail] = useState('admin@example.com')
  const [password, setPassword] = useState(SEED_PASSWORD)
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      if (mode === 'signup') {
        await signup(email, password)
        setMode('login')
      } else {
        await login(email, password)
        nav('/tickets')
      }
    } catch (err) {
      if (err instanceof ApiError) setError(err)
      else throw err
    } finally {
      setBusy(false)
    }
  }

  async function quick(acc: (typeof SEED_ACCOUNTS)[number]) {
    setError(null)
    setEmail(acc.email)
    setPassword(SEED_PASSWORD)
    try {
      if (user) await logout()
      await login(acc.email, SEED_PASSWORD)
      nav('/tickets')
    } catch (err) {
      if (err instanceof ApiError) setError(err)
      else throw err
    }
  }

  return (
    <div className="page">
      <h1>로그인</h1>
      <p className="lead">
        "누구인가" 를 서버가 알게 되는 과정이에요. 비밀번호는 <Term t="해시 / salt">해시</Term>로만 저장되고, 맞으면 서버가{' '}
        <Term t="JWT / claim">JWT</Term> 를 만들어 <Term t="HttpOnly / SameSite">HttpOnly 쿠키</Term>로 심어 줘요.
      </p>

      {user && (
        <div className="card">
          지금 <strong>{user.email}</strong> ({user.role}) 으로 로그인돼 있어요.{' '}
          <button className="ghost small" onClick={() => void logout()}>로그아웃</button>
        </div>
      )}

      <section className="card">
        <h3>빠른 로그인 (seed 계정)</h3>
        <div className="accounts">
          {SEED_ACCOUNTS.map((a) => (
            <button key={a.email} className="account" onClick={() => void quick(a)} disabled={busy}>
              <span className={`role role-${a.role}`}>{a.role}</span>
              <code>{a.email}</code>
              <span className="muted small">{a.groups !== '-' && `그룹 ${a.groups} · `}{a.note}</span>
            </button>
          ))}
        </div>
        <p className="muted small">계정이 없다고 나오면 터미널에서 <code>uv run python -m app.scripts.seed</code> 를 한 번 실행하세요.</p>
      </section>

      <form className="card form" onSubmit={(e) => void submit(e)}>
        <h3>{mode === 'login' ? '직접 로그인' : '회원가입'}</h3>
        <label>
          이메일
          <input value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
        </label>
        <label>
          비밀번호 <span className="muted small">(8자 이상)</span>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        </label>
        <div className="row">
          <button type="submit" disabled={busy}>{mode === 'login' ? '로그인' : '가입'}</button>
          <button type="button" className="ghost" onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}>
            {mode === 'login' ? '처음이면 가입하기' : '로그인으로'}
          </button>
        </div>
        <ErrorLine error={error} />
      </form>

      <Explain title="로그인 한 번에 일어나는 일">
        <ol>
          <li><code>POST /auth/login</code> 에 이메일·비밀번호를 JSON 으로 보냄 (오른쪽 패널 "요청/응답" 탭에서 확인)</li>
          <li>서버: 이메일로 사용자를 찾고, 입력한 비밀번호를 다시 해시해서 저장된 해시와 비교 (<code>bcrypt.checkpw</code>)</li>
          <li>맞으면 <code>{'{sub: 사용자id, role, groups, exp}'}</code> 를 <code>JWT_SECRET</code> 으로 서명 → 토큰</li>
          <li>응답 헤더 <code>Set-Cookie: access_token=…; HttpOnly; SameSite=lax</code> — 본문에는 토큰이 <strong>없어요</strong></li>
          <li>이후 모든 요청에 브라우저가 쿠키를 자동으로 붙임. 프론트 코드는 <code>credentials: 'include'</code> 한 줄이면 끝</li>
        </ol>
        <p className="muted small">
          확인: 브라우저 DevTools → Application → Cookies → localhost 에 <code>access_token</code> 이 보이지만 <code>document.cookie</code> 로는 안 읽혀요 (HttpOnly).
        </p>
      </Explain>

      <Explain title="틀린 비밀번호와 없는 이메일이 같은 메시지인 이유">
        <p>
          둘을 구분해 주면 공격자가 "이 이메일은 가입돼 있구나" 를 알게 돼요. 그래서 일부러 <code>Invalid email or password</code> 하나로 통일해요. 위 폼에서 둘 다
          시도해 보세요.
        </p>
      </Explain>

      <Explain title="왜 localStorage 가 아니라 쿠키인가">
        <table>
          <thead><tr><th></th><th>localStorage + Authorization 헤더</th><th>HttpOnly 쿠키 (여기)</th></tr></thead>
          <tbody>
            <tr><td>프론트가 할 일</td><td>토큰 저장, 매 요청 헤더 붙이기</td><td>없음</td></tr>
            <tr><td>XSS 로 토큰 탈취</td><td>가능 (JS 로 읽힘)</td><td>불가 (HttpOnly)</td></tr>
            <tr><td>CSRF</td><td>안전</td><td><code>SameSite=lax</code> 로 완화</td></tr>
          </tbody>
        </table>
        <p>회사 백엔드도 쿠키 방식이에요.</p>
      </Explain>
    </div>
  )
}
