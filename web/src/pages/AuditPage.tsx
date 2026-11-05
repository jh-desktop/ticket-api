import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, get } from '../api/client'
import type { AuditLog, User } from '../api/types'
import { ErrorLine, Explain } from '../components/Explain'
import { Term } from '../components/Term'
import { useAuth } from '../state/auth'

const ACTION_LABEL: Record<string, string> = {
  'ticket.created': '생성',
  'ticket.updated': '수정',
  'ticket.approved': '승인',
  'ticket.rejected': '반려',
  'ticket.deleted': '삭제',
}

export function AuditPage() {
  const { user } = useAuth()
  const [logs, setLogs] = useState<AuditLog[] | null>(null)
  const [users, setUsers] = useState<Map<string, User>>(new Map())
  const [error, setError] = useState<ApiError | null>(null)
  const [ticketId, setTicketId] = useState('')

  const load = useCallback(async () => {
    setError(null)
    try {
      const q = ticketId ? `?ticket_id=${encodeURIComponent(ticketId)}&limit=100` : '?limit=100'
      const [l, u] = await Promise.all([get<AuditLog[]>(`/audit-logs${q}`), get<User[]>('/users?limit=200').catch(() => [] as User[])])
      setLogs(l)
      setUsers(new Map(u.map((x) => [x.id, x])))
    } catch (e) {
      if (e instanceof ApiError) { setError(e); setLogs([]) } else throw e
    }
  }, [ticketId])

  useEffect(() => {
    if (user) void load()
  }, [user, load])

  const who = (id: string) => users.get(id)?.email ?? (id === 'system' ? 'system' : id.slice(-6))

  return (
    <div className="page">
      <h1>감사 로그</h1>
      <p className="lead">
        "누가 언제 무엇을 어떻게 바꿨나" 의 기록이에요. 티켓 서비스가 변경할 때마다 <Term t="감사 로그">감사 서비스</Term>를 불러 남겨요. 고치거나 지우는 API 는 일부러
        없어요.
      </p>

      {!user && <p className="card">먼저 <Link to="/login">로그인</Link>하세요. 이 화면은 ADMIN 전용이에요.</p>}
      {user && user.role !== 'ADMIN' && (
        <div className="card">
          <p><strong>{user.role}</strong> 은 볼 수 없어요. 그래도 서버에 물어봤고, 오른쪽 패널에 <code>require_role(ADMIN) DENIED</code> 가 찍혔을 거예요.</p>
          <ErrorLine error={error} />
          <p className="muted small"><Link to="/roles">역할 체험</Link>에서 admin 으로 바꾸면 보여요.</p>
        </div>
      )}

      {user?.role === 'ADMIN' && (
        <>
          <div className="row">
            <input placeholder="ticket_id 로 필터 (비우면 전체)" value={ticketId} onChange={(e) => setTicketId(e.target.value)} />
            <button className="ghost" onClick={() => void load()}>새로고침</button>
          </div>
          <ErrorLine error={error} />
          <ol className="timeline">
            {logs === null && <li className="muted">불러오는 중…</li>}
            {logs?.length === 0 && <li className="muted">기록이 없어요. 티켓 화면에서 뭔가 바꿔 보세요.</li>}
            {logs?.map((l) => (
              <li key={l.id} className={`a-${l.action.split('.')[1]}`}>
                <div className="when small muted">{new Date(l.created_at).toLocaleString()}</div>
                <div className="what">
                  <span className="badge">{ACTION_LABEL[l.action] ?? l.action}</span>
                  <strong>{who(l.actor)}</strong>
                  <span className="muted small"> · 티켓 <button className="link" onClick={() => setTicketId(l.ticket_id)}>{l.ticket_id.slice(-6)}</button></span>
                </div>
                <Diff before={l.before} after={l.after} />
              </li>
            ))}
          </ol>
        </>
      )}

      <Explain title="before / after 를 바뀐 필드만 남기는 이유">
        <p>
          수정 로그는 전체 문서가 아니라 <em>바뀐 필드만</em> 남겨요. 로그가 작아지고 "뭐가 바뀌었나" 가 바로 보여요. 생성은 before 가 없고, 삭제는 after 가 없어서 로그만 봐도
          무슨 일인지 알 수 있어요.
        </p>
        <p>409 로 거부된 승인 시도는 기록되지 않아요. <em>실제로 바뀐 것</em>만 기록하는 거예요.</p>
      </Explain>

      <Explain title="서비스가 서비스를 부른다">
        <pre className="json">{`class TicketService:
    def __init__(self, repo, audit: AuditService): ...

    async def approve(self, actor, ticket_id):
        ...
        await self._audit.record(ticket_id=..., action="ticket.approved",
                                 actor=actor.id, before={"status": "open"}, after={"status": "approved"})`}</pre>
        <p>티켓 서비스는 감사 <em>리포지토리</em>를 직접 만지지 않고 감사 <em>서비스</em>를 불러요. 층을 건너뛰지 않는 규칙이에요. 오른쪽 패널에서 승인 요청의 마지막 단계가 <code>AuditRepository.insert</code> 인 걸 확인하세요.</p>
      </Explain>
    </div>
  )
}

function Diff({ before, after }: { before: Record<string, unknown> | null; after: Record<string, unknown> | null }) {
  const keys = Array.from(new Set([...Object.keys(before ?? {}), ...Object.keys(after ?? {})]))
  if (keys.length === 0) return null
  return (
    <table className="diff">
      <tbody>
        {keys.map((k) => (
          <tr key={k}>
            <td className="k"><code>{k}</code></td>
            <td className="b">{before && k in before ? fmt(before[k]) : <span className="muted">—</span>}</td>
            <td className="arrow">→</td>
            <td className="a">{after && k in after ? fmt(after[k]) : <span className="muted">—</span>}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function fmt(v: unknown): string {
  if (v === null || v === undefined) return 'null'
  return typeof v === 'string' ? v : JSON.stringify(v)
}
