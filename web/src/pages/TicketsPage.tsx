import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, del, get, patch, post } from '../api/client'
import type { Ticket } from '../api/types'
import { ErrorLine, Explain } from '../components/Explain'
import { Term } from '../components/Term'
import { useAuth } from '../state/auth'

export function TicketsPage() {
  const { user } = useAuth()
  const [tickets, setTickets] = useState<Ticket[] | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [group, setGroup] = useState('')

  const canApprove = user?.role === 'ADMIN' || user?.role === 'GROUP_WRITER'
  const groups = useMemo(
    () => (user?.role === 'ADMIN' ? ['backend', 'mobile', 'security'] : (user?.groups ?? [])),
    [user],
  )

  const load = useCallback(async () => {
    setError(null)
    try {
      setTickets(await get<Ticket[]>('/tickets?limit=100'))
    } catch (e) {
      if (e instanceof ApiError) { setError(e); setTickets([]) } else throw e
    }
  }, [])

  useEffect(() => {
    if (user) void load()
    else setTickets(null)
  }, [user, load])

  useEffect(() => {
    if (!group && groups[0]) setGroup(groups[0])
  }, [groups, group])

  async function run(fn: () => Promise<unknown>) {
    setError(null)
    try {
      await fn()
      await load()
    } catch (e) {
      if (e instanceof ApiError) setError(e)
      else throw e
    }
  }

  function create(e: FormEvent) {
    e.preventDefault()
    void run(async () => {
      await post<Ticket>('/tickets', { title, description: description || null, group_id: group })
      setTitle('')
      setDescription('')
    })
  }

  if (!user) {
    return (
      <div className="page">
        <h1>티켓</h1>
        <p className="lead">먼저 <Link to="/login">로그인</Link>하세요. 로그인 없이 <code>GET /tickets</code> 를 부르면 어떻게 되는지 보고 싶으면 아래 버튼을 눌러 보세요.</p>
        <button onClick={() => void run(() => get('/tickets'))}>로그인 없이 GET /tickets 시도</button>
        <ErrorLine error={error} />
        <Explain title="401 이 나온 이유">
          <p>미들웨어가 쿠키에 토큰이 없는 걸 보고 라우터까지 가기 전에 끊었어요. 오른쪽 "요청 흐름" 패널에 <code>middleware:auth DENIED</code> 하나만 찍힌 걸 확인하세요.</p>
        </Explain>
      </div>
    )
  }

  return (
    <div className="page">
      <h1>티켓</h1>
      <p className="lead">
        <strong>{user.role}</strong> 으로 보고 있어요. 목록은 서버가 <Term t="스코핑">내 범위</Term>만 돌려준 거예요
        {user.role === 'ADMIN' && ' (ADMIN 은 전부)'}
        {(user.role === 'GROUP_WRITER' || user.role === 'GROUP_READER') && ` (그룹 ${user.groups.join(', ')} 의 티켓)`}
        {user.role === 'OWNER' && ' (내가 만든 것만)'}. 버튼을 누르고 오른쪽 패널에서 그 요청이 지난 길을 보세요.
      </p>

      {user.role !== 'GROUP_READER' ? (
        <form className="card form row-form" onSubmit={create}>
          <input placeholder="제목 (필수)" value={title} onChange={(e) => setTitle(e.target.value)} />
          <input placeholder="설명 (선택)" value={description} onChange={(e) => setDescription(e.target.value)} />
          <select value={group} onChange={(e) => setGroup(e.target.value)}>
            {groups.map((g) => <option key={g}>{g}</option>)}
            {user.role === 'ADMIN' && <option value="other-group">other-group</option>}
          </select>
          <button type="submit" disabled={!title || !group}>POST /tickets</button>
        </form>
      ) : (
        <div className="card muted">GROUP_READER 는 만들 수 없어요. (만들려고 하면 서비스의 <code>can_create</code> 에서 403 — <button className="link" onClick={() => void run(() => post('/tickets', { title: '시도', group_id: user.groups[0] ?? 'backend' }))}>직접 시도해 보기</button>)</div>
      )}

      <ErrorLine error={error} />

      <table className="tickets">
        <thead>
          <tr><th>상태</th><th>제목</th><th>그룹</th><th>소유자</th><th>행위</th></tr>
        </thead>
        <tbody>
          {tickets === null && <tr><td colSpan={5} className="muted">불러오는 중…</td></tr>}
          {tickets?.length === 0 && <tr><td colSpan={5} className="muted">보이는 티켓이 없어요. 하나 만들어 보세요.</td></tr>}
          {tickets?.map((t) => {
            const mine = t.owner_id === user.id
            return (
              <tr key={t.id}>
                <td><span className={`badge s-${t.status}`}>{t.status}</span></td>
                <td>
                  <div>{t.title}</div>
                  {t.description && <div className="muted small">{t.description}</div>}
                </td>
                <td><code>{t.group_id}</code></td>
                <td className="small">{mine ? <strong>나</strong> : <span className="muted" title={t.owner_id}>{t.owner_id.slice(-6)}</span>}</td>
                <td className="actions">
                  <button className="small" title="POST /tickets/{id}/approve" onClick={() => void run(() => post(`/tickets/${t.id}/approve`))} disabled={!canApprove || t.status !== 'open'}>승인</button>
                  <button className="small" title="POST /tickets/{id}/reject" onClick={() => void run(() => post(`/tickets/${t.id}/reject`))} disabled={!canApprove || t.status !== 'open'}>반려</button>
                  <button className="small ghost" title="PATCH /tickets/{id}" onClick={() => { const v = prompt('새 제목', t.title); if (v) void run(() => patch(`/tickets/${t.id}`, { title: v })) }}>수정</button>
                  <button className="small ghost danger" title="DELETE /tickets/{id}" onClick={() => void run(() => del(`/tickets/${t.id}`))}>삭제</button>
                  {!canApprove && t.status === 'open' && (
                    <button className="small link" title="역할상 안 되는 걸 일부러 시도" onClick={() => void run(() => post(`/tickets/${t.id}/approve`))}>승인 시도→?</button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <Explain title="승인 버튼 하나가 지나는 길">
        <ol>
          <li><strong>미들웨어</strong>: 쿠키의 토큰이 멀쩡한가 (서명·만료)</li>
          <li><strong>라우터</strong> <code>approve_ticket</code>: 입구에서 <code>require_role("ADMIN","GROUP_WRITER")</code> — 역할이 아니면 여기서 403</li>
          <li><strong>get_current_user</strong>: 토큰의 id 로 DB 에서 사용자 조회</li>
          <li><strong>서비스</strong> <code>TicketService.approve</code>: 티켓을 꺼내고(없거나 내 범위 밖이면 404) → 그 그룹의 WRITER 인가(아니면 403) → 상태 전이 표 확인(open 이 아니면 409)</li>
          <li><strong>리포지토리</strong>: <code>update</code> 로 status 변경, <code>AuditRepository.insert</code> 로 감사 로그</li>
        </ol>
        <p className="muted small">오른쪽 패널의 단계 목록이 정확히 이 순서로 찍혀요. 비활성화된 버튼은 프론트가 미리 막은 것이고, "승인 시도→?" 는 서버가 막는 걸 직접 보는 용도예요.</p>
      </Explain>

      <Explain title="상태코드 읽는 법">
        <table>
          <tbody>
            <tr><td><span className="status ok">201</span></td><td>만들어짐 (POST 성공)</td></tr>
            <tr><td><span className="status ok">204</span></td><td>성공, 돌려줄 본문 없음 (DELETE)</td></tr>
            <tr><td><span className="status warn">401</span></td><td>누구인지 모름 — 로그인 필요</td></tr>
            <tr><td><span className="status warn">403</span></td><td>누군지는 알지만 이 행위 권한 없음</td></tr>
            <tr><td><span className="status err">404</span></td><td>없음 — 또는 내 범위 밖 (존재를 숨김)</td></tr>
            <tr><td><span className="status err">409</span></td><td>지금 상태와 충돌 — 이미 승인된 티켓을 또 승인 등</td></tr>
            <tr><td><span className="status err">422</span></td><td>요청 모양이 틀림 — 빈 제목 등 (Pydantic)</td></tr>
          </tbody>
        </table>
      </Explain>
    </div>
  )
}
