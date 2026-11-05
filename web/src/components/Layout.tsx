import { NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../state/auth'
import { TracePanel } from './TracePanel'

const NAV: Array<{ to: string; label: string; sub: string }> = [
  { to: '/', label: '시스템 구조', sub: '전체 그림부터' },
  { to: '/login', label: '로그인', sub: '해시 · JWT · 쿠키' },
  { to: '/tickets', label: '티켓', sub: '요청이 지나는 길' },
  { to: '/roles', label: '역할 체험', sub: 'RBAC · 403 vs 404' },
  { to: '/audit', label: '감사 로그', sub: '시스템이 기록하는 것' },
  { to: '/snapshots', label: '스냅샷', sub: 'CronJob · 통계' },
  { to: '/glossary', label: '용어집', sub: '모르는 말 검색' },
  { to: '/docs', label: '학습 노트', sub: '주차별 정리' },
]

export function Layout() {
  const { user, logout } = useAuth()
  return (
    <div className="shell">
      <aside className="nav">
        <div className="brand">
          <strong>ticket-api</strong>
          <span className="muted small">백엔드 배우기</span>
        </div>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} className={({ isActive }) => (isActive ? 'on' : '')}>
              <span>{n.label}</span>
              <span className="muted small">{n.sub}</span>
            </NavLink>
          ))}
        </nav>
        <div className="me">
          {user ? (
            <>
              <div className="small">
                <strong>{user.email}</strong>
                <br />
                <span className={`role role-${user.role}`}>{user.role}</span>
                {user.groups.length > 0 && <span className="muted"> · {user.groups.join(', ')}</span>}
              </div>
              <button className="ghost small" onClick={() => void logout()}>로그아웃</button>
            </>
          ) : (
            <span className="muted small">로그인 안 됨</span>
          )}
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
      <aside className="side">
        <TracePanel />
      </aside>
    </div>
  )
}
