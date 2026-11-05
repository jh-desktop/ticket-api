import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { useGlossary } from '../state/glossary'

const WEEK: Record<string, string> = {
  week1: '1주차 FastAPI·Pydantic·Depends',
  week2: '2주차 MongoDB·리포지토리',
  week3: '3주차 서비스·예외·감사로그',
  week4: '4주차 인증·RBAC',
  week5: '5주차 테스트·타입·시드',
  week6: '6주차 스케줄러·Docker·K8s',
}

export function GlossaryPage() {
  const { entries } = useGlossary()
  const [params, setParams] = useSearchParams()
  const [q, setQ] = useState(params.get('q') ?? '')

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return entries
    return entries.filter((e) => [e.term, e.meaning, e.frontend].some((s) => s.toLowerCase().includes(needle)))
  }, [entries, q])

  const grouped = useMemo(() => {
    const m = new Map<string, typeof entries>()
    for (const e of filtered) m.set(e.source, [...(m.get(e.source) ?? []), e])
    return Array.from(m.entries()).sort(([a], [b]) => a.localeCompare(b))
  }, [filtered])

  return (
    <div className="page">
      <h1>용어집</h1>
      <p className="lead">
        각 주차 학습 노트의 "용어 정리" 표를 모은 거예요 ({entries.length}개). 본문에서 점선 밑줄 친 말을 클릭해도 여기로 와요. 오른쪽 열은 프론트에서 비슷한 것.
      </p>
      <input
        className="search"
        placeholder="검색 — 예: 쿠키, fixture, 커서, 403"
        value={q}
        onChange={(e) => { setQ(e.target.value); setParams(e.target.value ? { q: e.target.value } : {}) }}
        autoFocus
      />
      {entries.length === 0 && <p className="muted">용어집을 못 받았어요. 백엔드(APP_ENV=dev)가 떠 있고 docs/ 폴더가 있는지 확인하세요.</p>}
      {grouped.map(([source, list]) => (
        <section key={source} className="card">
          <h3>{WEEK[source] ?? source}</h3>
          <table className="glossary">
            <tbody>
              {list.map((e, i) => (
                <tr key={i}>
                  <td className="term-cell"><strong>{e.term}</strong></td>
                  <td>{e.meaning}</td>
                  <td className="muted small">{e.frontend}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}
      {q && filtered.length === 0 && <p className="muted">"{q}" 에 해당하는 용어가 없어요.</p>}
    </div>
  )
}
