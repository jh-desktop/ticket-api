import { Link } from 'react-router-dom'

import { Explain } from '../components/Explain'
import { Term } from '../components/Term'
import { useAuth } from '../state/auth'
import { SEED_ACCOUNTS, SEED_PASSWORD } from './LoginPage'

type Cell = { text: string; kind: 'yes' | 'part' | 'no' }
const Y = (t: string): Cell => ({ text: t, kind: 'yes' })
const P = (t: string): Cell => ({ text: t, kind: 'part' })
const N = (t = '✗'): Cell => ({ text: t, kind: 'no' })

const MATRIX: Array<{ action: string; where: string; ADMIN: Cell; GROUP_WRITER: Cell; GROUP_READER: Cell; OWNER: Cell }> = [
  { action: '목록 조회', where: 'rbac.scope_filter → 쿼리 필터', ADMIN: Y('전부'), GROUP_WRITER: P('내 그룹'), GROUP_READER: P('내 그룹'), OWNER: P('내 것만') },
  { action: '범위 밖 티켓 조회', where: 'service.get → can_view', ADMIN: Y('200'), GROUP_WRITER: N('404'), GROUP_READER: N('404'), OWNER: N('404') },
  { action: '생성', where: 'service.create → can_create', ADMIN: Y('어디든'), GROUP_WRITER: P('내 그룹'), GROUP_READER: N('403'), OWNER: P('내 그룹') },
  { action: '수정·삭제', where: 'service → can_edit', ADMIN: Y('전부'), GROUP_WRITER: P('내 것'), GROUP_READER: N('403'), OWNER: P('내 것') },
  { action: '승인·반려', where: 'require_role + can_transition', ADMIN: Y('전부'), GROUP_WRITER: P('내 그룹'), GROUP_READER: N('403'), OWNER: N('403') },
  { action: '/users, /audit-logs, /snapshots', where: 'require_role("ADMIN")', ADMIN: Y('200'), GROUP_WRITER: N('403'), GROUP_READER: N('403'), OWNER: N('403') },
]
const ROLES = ['ADMIN', 'GROUP_WRITER', 'GROUP_READER', 'OWNER'] as const

export function RolesPage() {
  const { user, login, logout } = useAuth()

  async function become(email: string) {
    if (user) await logout()
    await login(email, SEED_PASSWORD)
  }

  return (
    <div className="page">
      <h1>역할 체험</h1>
      <p className="lead">
        같은 화면, 같은 데이터인데 <Term t="RBAC">역할</Term>에 따라 보이는 것과 되는 것이 달라요. 아래에서 계정을 바꿔 가며{' '}
        <Link to="/tickets">티켓</Link> 화면을 다시 보세요.
      </p>

      <section className="card">
        <h3>계정 바꾸기</h3>
        <div className="accounts">
          {SEED_ACCOUNTS.map((a) => (
            <button key={a.email} className={`account ${user?.email === a.email ? 'on' : ''}`} onClick={() => void become(a.email)}>
              <span className={`role role-${a.role}`}>{a.role}</span>
              <code>{a.email}</code>
              <span className="muted small">{a.groups !== '-' && `그룹 ${a.groups} · `}{a.note}</span>
            </button>
          ))}
        </div>
      </section>

      <table className="matrix">
        <thead>
          <tr>
            <th>행위</th>
            <th className="muted small">어디서 판단하나</th>
            {ROLES.map((r) => (
              <th key={r} className={user?.role === r ? 'me' : ''}>
                <span className={`role role-${r}`}>{r}</span>
                {user?.role === r && <div className="small">← 지금 나</div>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {MATRIX.map((row) => (
            <tr key={row.action}>
              <td>{row.action}</td>
              <td className="muted small"><code>{row.where}</code></td>
              {ROLES.map((r) => (
                <td key={r} className={`cell-${row[r].kind} ${user?.role === r ? 'me' : ''}`}>{row[r].text}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <Explain title="인증과 인가는 다른 질문이에요">
        <ul>
          <li><strong>인증 (authentication)</strong> — 누구인가. 로그인, 토큰. 실패하면 <span className="status warn">401</span>.</li>
          <li><strong>인가 (authorization)</strong> — 무엇을 할 수 있나. 역할, 그룹. 실패하면 <span className="status warn">403</span>.</li>
        </ul>
        <p>미들웨어와 <code>get_current_user</code> 가 인증을, <code>core/rbac.py</code> 가 인가를 맡아요. 파일이 다른 건 질문이 다르기 때문이에요.</p>
      </Explain>

      <Explain title="403 과 404 를 나누는 기준">
        <p>
          <strong>볼 수 없는 티켓</strong>은 <span className="status err">404</span>. "권한 없음" 이라고 하면 "그 id 의 티켓이 존재한다" 는 사실이 새어 나가요. 그래서 없는 척해요.
          <br />
          <strong>볼 수는 있지만 할 수 없는 행위</strong>는 <span className="status warn">403</span>. 같은 그룹 READER 가 수정하려 할 때.
        </p>
        <p className="muted small">owner2 로 로그인해서 owner1 의 티켓 id 로 <code>GET /tickets/&#123;id&#125;</code> 를 부르면 404 가 나요. (id 는 admin 으로 로그인했을 때 목록에서 볼 수 있어요)</p>
      </Explain>

      <Explain title="인가가 '필터' 로 나타나는 곳">
        <pre className="json">{`def scope_filter(user):
    if user.role == "ADMIN":              return {}
    if user.role in ("GROUP_WRITER", "GROUP_READER"):
                                          return {"group_id": {"$in": user.groups}}
    return {"owner_id": user.id}          # OWNER`}</pre>
        <p>
          목록 조회에는 "거부" 가 없어요. 이 dict 가 Mongo 쿼리에 그대로 섞여서 <em>볼 수 있는 것만</em> 결과에 나와요. 오른쪽 패널에서 <code>GET /tickets</code> 의 단계에{' '}
          <code>rbac:scope_filter for OWNER</code> 처럼 찍히는 걸 보세요.
        </p>
      </Explain>

      <Explain title="두 단계 검사">
        <p>
          승인은 라우터 입구 <code>require_role("ADMIN","GROUP_WRITER")</code> 에서 <em>역할 자체</em>를 거르고, 서비스 안 <code>can_transition</code> 에서 <em>어느 그룹의
          티켓인가</em>를 봐요. 거친 검사는 입구, 세밀한 검사는 안쪽. 오른쪽 패널에서 OWNER 의 승인 시도는 <code>require_role … DENIED</code> 에서 끝나고 서비스 단계가 아예
          없는 걸 확인하세요.
        </p>
      </Explain>
    </div>
  )
}
