import { useState } from 'react'

import type { ApiCall } from '../api/client'
import { useCalls } from '../state/calls'
import { JsonView } from './JsonView'

/** 레이어 순서 (백엔드 /learn/structure 의 request_flow 와 같다) */
const LAYERS: Array<{ key: string; name: string; hint: string }> = [
  { key: 'middleware', name: '미들웨어', hint: 'server.py — 토큰이 있고 멀쩡한가' },
  { key: 'router', name: '라우터', hint: 'api/v1/*.py — 요청 받기, 응답 돌려주기' },
  { key: 'auth', name: '인증·인가', hint: 'core/auth.py, core/rbac.py — 누구인가, 해도 되나' },
  { key: 'service', name: '서비스', hint: 'services/*.py — 비즈니스 규칙' },
  { key: 'repository', name: '리포지토리', hint: 'repositories/*.py — Mongo 쿼리' },
  { key: 'db', name: 'MongoDB', hint: '컬렉션에 읽고 쓰기' },
]

function layerOf(step: string): string {
  const prefix = step.split(':')[0] ?? ''
  if (prefix === 'rbac') return 'auth'
  return prefix
}

function pretty(step: string): { layer: string; text: string; denied: boolean } {
  const [prefix, ...rest] = step.split(':')
  const text = rest.join(':').trim()
  return { layer: layerOf(step), text: text || (prefix ?? step), denied: /DENIED/.test(step) }
}

function statusClass(status: number): string {
  if (status < 300) return 'ok'
  if (status === 401 || status === 403) return 'warn'
  return 'err'
}

export function TracePanel() {
  const { calls, selected, select } = useCalls()
  const [tab, setTab] = useState<'flow' | 'io' | 'history'>('flow')

  if (!selected) {
    return (
      <section className="panel">
        <h3>요청 흐름</h3>
        <p className="muted">아직 요청이 없어요. 왼쪽에서 뭔가 눌러 보세요. 그 요청이 서버의 어느 레이어를 지났는지 여기 그려져요.</p>
        <Layers active={new Set()} />
      </section>
    )
  }

  const touched = new Set(selected.trace.map(layerOf))
  if (selected.trace.some((s) => s.startsWith('repository:'))) touched.add('db')

  return (
    <section className="panel">
      <header className="panel-head">
        <h3>요청 흐름</h3>
        <div className="tabs">
          <button className={tab === 'flow' ? 'on' : ''} onClick={() => setTab('flow')}>흐름</button>
          <button className={tab === 'io' ? 'on' : ''} onClick={() => setTab('io')}>요청/응답</button>
          <button className={tab === 'history' ? 'on' : ''} onClick={() => setTab('history')}>기록 {calls.length}</button>
        </div>
      </header>

      <CallLine call={selected} />

      {tab === 'flow' && (
        <>
          <Layers active={touched} />
          <ol className="steps">
            {selected.trace.length === 0 && <li className="muted small">추적 정보 없음 (APP_ENV=dev 에서만 X-Trace 헤더가 붙어요)</li>}
            {selected.trace.map((s, i) => {
              const p = pretty(s)
              return (
                <li key={i} className={p.denied ? 'denied' : ''}>
                  <span className={`chip layer-${p.layer}`}>{LAYERS.find((l) => l.key === p.layer)?.name ?? p.layer}</span>
                  <code>{p.text}</code>
                </li>
              )
            })}
          </ol>
          <Verdict call={selected} />
        </>
      )}

      {tab === 'io' && (
        <div className="io">
          <h4>요청</h4>
          <code className="small">{selected.method} /api{selected.path}</code>
          <JsonView value={selected.requestBody} empty="(본문 없음)" />
          <h4>응답 {selected.status}</h4>
          <JsonView value={selected.responseBody} empty="(본문 없음 — 204 등)" />
          <p className="muted small">
            브라우저 왕복 {selected.clientMs}ms
            {selected.serverMs !== null && <> · 서버 처리 {selected.serverMs}ms</>}
            {selected.requestId && <> · 요청 id {selected.requestId}</>}
          </p>
        </div>
      )}

      {tab === 'history' && (
        <ul className="history">
          {calls.map((c) => (
            <li key={c.id}>
              <button className={c.id === selected.id ? 'on' : ''} onClick={() => { select(c); setTab('flow') }}>
                <CallLine call={c} compact />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function CallLine({ call, compact = false }: { call: ApiCall; compact?: boolean }) {
  return (
    <div className={`callline ${compact ? 'compact' : ''}`}>
      <span className={`status ${statusClass(call.status)}`}>{call.status}</span>
      <code>
        {call.method} {call.path}
      </code>
      {!compact && <span className="muted small">{call.at.toLocaleTimeString()}</span>}
    </div>
  )
}

function Layers({ active }: { active: Set<string> }) {
  return (
    <div className="layers">
      {LAYERS.map((l, i) => (
        <div key={l.key} className={`layer layer-${l.key} ${active.has(l.key) ? 'active' : ''}`} title={l.hint}>
          <span className="n">{i + 1}</span>
          <span>{l.name}</span>
        </div>
      ))}
    </div>
  )
}

/** 결과 한 줄 해설: 어디서 멈췄나 / 왜 그 상태코드인가 */
function Verdict({ call }: { call: ApiCall }) {
  const denied = call.trace.find((s) => /DENIED/.test(s))
  let text: string
  if (call.status === 401) text = '401 — 누구인지 모름. 토큰이 없거나 만료/위조. 미들웨어 또는 get_current_user 에서 끝났고, 서비스까지 가지 않았어요.'
  else if (call.status === 403) text = denied?.startsWith('rbac:require_role')
    ? '403 — 역할 자체가 안 됨. 라우터 입구의 require_role 에서 막혔어요 (서비스 호출 전).'
    : '403 — 볼 수는 있지만 이 행위는 못 함. 서비스 안의 rbac.ensure 에서 막혔어요.'
  else if (call.status === 404) text = '404 — 없거나, 있어도 내 범위 밖. 범위 밖 티켓은 존재를 숨기려고 403 이 아니라 404 를 줘요.'
  else if (call.status === 409) text = '409 — 요청은 멀쩡하지만 현재 상태와 충돌 (상태 전이 규칙 / 중복 이메일).'
  else if (call.status === 422) text = '422 — 요청 모양이 틀림. Pydantic 검증에서 끝났고 라우터 함수 본문은 실행되지 않았어요.'
  else if (call.status >= 500) text = '5xx — 서버 내부 오류. 서버 로그를 보세요.'
  else {
    const repoWrites = call.trace.filter((s) => /repository:.*\.(insert|create|update|delete)/.test(s)).length
    const audit = call.trace.some((s) => s.includes('AuditRepository.insert'))
    text = `${call.status} — 성공. 레이어 ${new Set(call.trace.map(layerOf)).size}개를 지났고, DB 쓰기 ${repoWrites}회${audit ? ' (감사 로그 포함)' : ''}.`
  }
  return <p className="verdict">{text}</p>
}
