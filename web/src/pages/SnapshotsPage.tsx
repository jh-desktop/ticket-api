import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { ApiError, get, post } from '../api/client'
import type { Snapshot } from '../api/types'
import { ErrorLine, Explain } from '../components/Explain'
import { Term } from '../components/Term'
import { useAuth } from '../state/auth'

/*
 * 색: 상태 3개는 "식별" 이므로 범주형. 엔티티별로 고정 (순위·순서로 바꾸지 않음).
 * 값은 dataviz 기준 팔레트의 1·3·2 슬롯, 라이트/다크 각각 validate_palette.js 로 검증한 값.
 * 그룹별 막대는 단일 시리즈라 한 가지 색(시퀀셜 파랑 한 단계).
 */
const SERIES: Record<'open' | 'approved' | 'rejected', { label: string; light: string; dark: string }> = {
  open: { label: '열림', light: '#2a78d6', dark: '#3987e5' },
  approved: { label: '승인', light: '#1baf7a', dark: '#199e70' },
  rejected: { label: '반려', light: '#eb6834', dark: '#d95926' },
}
const ORDER = ['open', 'approved', 'rejected'] as const

function useDark(): boolean {
  const [dark, setDark] = useState(() => window.matchMedia('(prefers-color-scheme: dark)').matches)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const on = (e: MediaQueryListEvent) => setDark(e.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return dark
}

const fmtTime = (iso: string) => {
  const d = new Date(iso)
  return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

interface Point {
  t: string
  label: string
  total: number
  open: number
  approved: number
  rejected: number
}

export function SnapshotsPage() {
  const { user } = useAuth()
  const dark = useDark()
  const [snaps, setSnaps] = useState<Snapshot[] | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [showTable, setShowTable] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setError(null)
    try {
      setSnaps(await get<Snapshot[]>('/snapshots?limit=200'))
    } catch (e) {
      if (e instanceof ApiError) { setError(e); setSnaps([]) } else throw e
    }
  }, [])

  useEffect(() => {
    if (user) void load()
  }, [user, load])

  async function takeNow() {
    setBusy(true)
    setError(null)
    try {
      await post('/scheduler/snapshots') // 무인증 — CronJob 이 부르는 그 엔드포인트
      await load()
    } catch (e) {
      if (e instanceof ApiError) setError(e)
      else throw e
    } finally {
      setBusy(false)
    }
  }

  const points: Point[] = useMemo(
    () =>
      (snaps ?? [])
        .slice()
        .reverse() // API 는 최신순 → 차트는 오래된 것부터
        .map((s) => ({
          t: s.taken_at,
          label: fmtTime(s.taken_at),
          total: s.total,
          open: s.by_status.open ?? 0,
          approved: s.by_status.approved ?? 0,
          rejected: s.by_status.rejected ?? 0,
        })),
    [snaps],
  )
  const latest = snaps?.[0] ?? null
  const groups = useMemo(
    () => Object.entries(latest?.by_group ?? {}).map(([g, n]) => ({ group: g, count: n })).sort((a, b) => b.count - a.count),
    [latest],
  )
  const color = (k: keyof typeof SERIES) => (dark ? SERIES[k].dark : SERIES[k].light)
  const barColor = dark ? '#3987e5' : '#2a78d6'

  return (
    <div className="page">
      <h1>스냅샷</h1>
      <p className="lead">
        <Term t="CronJob">외부 스케줄러</Term>가 5분마다 <code>POST /scheduler/snapshots</code> 를 불러 "그 시각의 티켓 개수" 를 한 장씩 저장해요. 지금 개수는
        tickets 를 세면 되지만, <em>어제 이 시간엔 몇 개였나</em> 는 이 기록이 있어야 알 수 있어요.
      </p>

      {!user && <p className="card">먼저 <Link to="/login">로그인</Link>하세요. 이력 조회는 ADMIN 전용이에요 (스냅샷 찍기 자체는 누구나 — 무인증 경로).</p>}

      <div className="row">
        <button onClick={() => void takeNow()} disabled={busy}>지금 스냅샷 찍기 (POST /scheduler/snapshots)</button>
        {user?.role === 'ADMIN' && <button className="ghost" onClick={() => setShowTable((v) => !v)}>{showTable ? '차트로' : '표로 보기'}</button>}
      </div>
      <ErrorLine error={error} />

      {user && user.role !== 'ADMIN' && (
        <div className="card">
          <strong>{user.role}</strong> 은 이력을 볼 수 없어요 (<code>require_role("ADMIN")</code>). 위 버튼으로 스냅샷을 찍는 건 돼요 — 그 요청은 미들웨어의 <code>_NO_AUTH_PREFIXES</code> 를 통과하니까요. 오른쪽 패널에서 두 요청의 흐름을 비교해 보세요.
        </div>
      )}

      {user?.role === 'ADMIN' && latest && (
        <>
          <div className="stat-row">
            <div className="stat"><div className="v">{latest.total}</div><div className="k">전체 · {fmtTime(latest.taken_at)} 기준</div></div>
            {ORDER.map((k) => (
              <div className="stat" key={k}>
                <div className="v" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 3, background: color(k), display: 'inline-block' }} />
                  {latest.by_status[k] ?? 0}
                </div>
                <div className="k">{SERIES[k].label}</div>
              </div>
            ))}
          </div>

          {showTable ? (
            <table className="card">
              <thead><tr><th>시각</th><th>전체</th>{ORDER.map((k) => <th key={k}>{SERIES[k].label}</th>)}<th>그룹별</th></tr></thead>
              <tbody>
                {snaps?.map((s) => (
                  <tr key={s.id}>
                    <td>{fmtTime(s.taken_at)}</td>
                    <td>{s.total}</td>
                    {ORDER.map((k) => <td key={k}>{s.by_status[k] ?? 0}</td>)}
                    <td className="small muted">{Object.entries(s.by_group).map(([g, n]) => `${g} ${n}`).join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <>
              <section className="chart-card">
                <div className="chart-head">
                  <h3>상태별 티켓 수 추이</h3>
                  <div className="legend">
                    {ORDER.map((k) => <span key={k} style={{ ['--sw' as string]: color(k) }}>{SERIES[k].label}</span>)}
                  </div>
                </div>
                {points.length < 2 && <p className="muted small">점이 {points.length}개뿐이라 선이 안 보여요. 티켓을 몇 개 만들고 "지금 스냅샷 찍기" 를 두세 번 눌러 보세요.</p>}
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={points} margin={{ top: 12, right: 48, left: 0, bottom: 4 }}>
                    <CartesianGrid vertical={false} stroke="var(--line)" />
                    <XAxis dataKey="label" tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={{ stroke: 'var(--line)' }} tickLine={false} minTickGap={24} />
                    <YAxis allowDecimals={false} width={32} tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTip />} cursor={{ stroke: 'var(--muted)', strokeWidth: 1 }} />
                    {ORDER.map((k) => (
                      <Line
                        key={k}
                        type="monotone"
                        dataKey={k}
                        name={SERIES[k].label}
                        stroke={color(k)}
                        strokeWidth={2}
                        dot={{ r: 4, fill: color(k), stroke: 'var(--surface)', strokeWidth: 2 }}
                        activeDot={{ r: 5 }}
                        isAnimationActive={false}
                        label={(p: { x?: number | string; y?: number | string; index?: number; value?: unknown }) =>
                          p.index === points.length - 1 && p.x !== undefined && p.y !== undefined
                            ? <text x={Number(p.x) + 10} y={Number(p.y) + 4} fill="var(--ink-2)" fontSize={12}>{SERIES[k].label} {String(p.value)}</text>
                            : <g />
                        }
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </section>

              <section className="chart-card">
                <div className="chart-head"><h3>그룹별 티켓 수 (최신 스냅샷)</h3></div>
                {groups.length === 0 ? (
                  <p className="muted small">그룹 데이터 없음</p>
                ) : (
                  <ResponsiveContainer width="100%" height={Math.max(80, groups.length * 34 + 24)}>
                    <BarChart data={groups} layout="vertical" margin={{ top: 4, right: 40, left: 8, bottom: 4 }} barCategoryGap={8}>
                      <CartesianGrid horizontal={false} stroke="var(--line)" />
                      <XAxis type="number" allowDecimals={false} tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={{ stroke: 'var(--line)' }} tickLine={false} />
                      <YAxis type="category" dataKey="group" width={90} tick={{ fill: 'var(--ink-2)', fontSize: 12.5 }} axisLine={false} tickLine={false} />
                      <Tooltip content={<ChartTip />} cursor={{ fill: 'var(--surface-2)' }} />
                      <Bar dataKey="count" name="티켓" fill={barColor} barSize={14} radius={[0, 4, 4, 0]} isAnimationActive={false}
                        label={{ position: 'right', fill: 'var(--ink-2)', fontSize: 12 }} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </section>
            </>
          )}
        </>
      )}
      {user?.role === 'ADMIN' && snaps?.length === 0 && <p className="card muted">아직 스냅샷이 없어요. 위 버튼을 눌러 첫 장을 찍어 보세요.</p>}

      <Explain title="왜 앱 안에서 5분마다 돌리지 않나요?">
        <p>
          운영에서 앱은 <Term t="레플리카">레플리카</Term> 2개 이상으로 떠요. 앱 안에 타이머를 두면 <strong>각 프로세스가 자기 타이머를 가져서 2번 실행</strong>돼요. 밖의
          CronJob 이 HTTP 로 한 번 부르면 Service 가 그중 하나에만 전달해서 1번만 실행돼요.
        </p>
        <pre className="json">{`# k8s/cronjob.yaml
schedule: "*/5 * * * *"
args: [-fsS, -X, POST, http://ticket-api/scheduler/snapshots]`}</pre>
        <p>앱 코드엔 "무엇을 하나"(<code>SnapshotService.take</code>)만 있고 "언제 하나" 는 저 YAML 에 있어요. 주기를 바꾸려면 코드 수정 없이 저 한 줄.</p>
      </Explain>

      <Explain title="무인증인데 안전한가요?">
        <p>
          <code>/scheduler/*</code> 는 로그인 없이 열려 있어요 (CronJob 은 로그인을 못 하니까). 대신 K8s Service 가 <code>ClusterIP</code> 라 클러스터 밖에서는 아예 닿지 않아요.
          "인증으로 막을 것" 과 "네트워크로 막을 것" 을 구분하는 거예요. 지금 로컬에서 버튼이 눌리는 건 같은 PC 라서예요.
        </p>
      </Explain>

      <Explain title="세는 법: aggregation">
        <pre className="json">{`pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
# → {"open": 3, "approved": 2, "rejected": 1}`}</pre>
        <p>SQL 의 <code>GROUP BY</code> 예요. 서비스는 없는 상태를 0 으로 채워서 차트 키가 들쭉날쭉하지 않게 해요.</p>
      </Explain>
    </div>
  )
}

/** 툴팁. 텍스트는 잉크 색, 시리즈 색은 옆의 점이 든다. */
function ChartTip(props: { active?: boolean; label?: unknown; payload?: ReadonlyArray<{ name?: unknown; value?: unknown; color?: string; fill?: string }> }) {
  if (!props.active || !props.payload?.length) return null
  return (
    <div className="tip">
      <b>{String(props.label ?? '')}</b>
      {props.payload.map((p, i) => (
        <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: p.color ?? p.fill, display: 'inline-block' }} />
          <span style={{ color: 'var(--ink-2)' }}>{String(p.name ?? '')}</span>
          <strong style={{ marginLeft: 'auto' }}>{String(p.value ?? '')}</strong>
        </div>
      ))}
    </div>
  )
}
