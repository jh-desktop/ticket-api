import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { get } from '../api/client'
import type { Structure } from '../api/types'
import { Explain } from '../components/Explain'
import { Term } from '../components/Term'

export function StructurePage() {
  const [s, setS] = useState<Structure | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [openLayer, setOpenLayer] = useState<string>('router')

  useEffect(() => {
    get<Structure>('/learn/structure').then(setS).catch((e: Error) => setErr(e.message))
  }, [])

  if (err) return <p className="errorline">구조 정보를 못 가져왔어요: {err}. 백엔드가 떠 있나요? (uv run uvicorn app.server:app --reload)</p>
  if (!s) return <p className="muted">불러오는 중…</p>

  const layer = s.layers.find((l) => l.key === openLayer) ?? s.layers[0]!
  const files = s.files.filter((f) => f.layer === layer.key)

  return (
    <div className="page">
      <h1>시스템 구조</h1>
      <p className="lead">
        이 프로젝트는 <strong>티켓 승인 시스템</strong>이에요. 사용자가 티켓을 만들고, 권한 있는 사람이 승인하거나 반려하고, 모든 변경이
        기록돼요. 백엔드는 <Term t="레이어">층</Term>으로 나뉘어 있고, 요청 하나는 아래 순서로 지나가요.
      </p>

      <ol className="flow">
        {s.request_flow.map((k, i) => {
          const l = s.layers.find((x) => x.key === k)!
          return (
            <li key={k}>
              <button className={`flow-item layer-${k} ${openLayer === k ? 'on' : ''}`} onClick={() => setOpenLayer(k)}>
                <span className="n">{i + 1}</span>
                <strong>{l.name}</strong>
                <span className="small muted">{l.folder}</span>
              </button>
            </li>
          )
        })}
      </ol>

      <section className={`card layer-${layer.key}`}>
        <h2>
          {layer.name} <span className="muted small">{layer.folder}</span>
        </h2>
        <p>{layer.role}</p>
        <div className="cols">
          <div>
            <h4>아는 것</h4>
            <ul>{layer.knows.map((k) => <li key={k}>{k}</li>)}</ul>
          </div>
          <div>
            <h4>모르는 것 (일부러)</h4>
            <ul>{layer.never.map((k) => <li key={k}>{k}</li>)}</ul>
          </div>
          <div>
            <h4>회사 레포에서는</h4>
            <code>{layer.company}</code>
          </div>
        </div>
        <h4>이 층의 파일</h4>
        <table className="files">
          <tbody>
            {files.map((f) => (
              <tr key={f.path}>
                <td><code>{f.path}</code></td>
                <td>{f.summary}</td>
                <td className="muted small">{f.company}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <Explain title="왜 층을 나누나요?">
        <p>
          한 파일에 다 쓰면 처음엔 빠르지만, "이 규칙 어디 있지?" 를 찾는 시간이 금방 코드 쓰는 시간을 넘어서요. 층을 나누면 질문이 단순해져요.
        </p>
        <ul>
          <li>상태코드·URL 이야기 → <strong>라우터</strong></li>
          <li>"이게 되는 일인가" → <strong>서비스</strong></li>
          <li>Mongo 문법 → <strong>리포지토리</strong></li>
        </ul>
        <p>
          그리고 각 층은 <em>아래층만</em> 불러요. 라우터가 리포지토리를 직접 부르지 않고, 서비스가 상태코드를 모르는 건 실수가 아니라 규칙이에요.
        </p>
        <p>
          오른쪽 <strong>요청 흐름</strong> 패널은 실제 요청이 어느 층을 지났는지 서버가 알려준 대로 그려요. <Link to="/tickets">티켓</Link> 화면에서 버튼을
          눌러 보세요.
        </p>
      </Explain>

      <Explain title="회사 레포를 읽을 때">
        <p>
          폴더 이름과 층 구조가 같아요. <code>tree -L 2</code> 로 폴더를 보고, 가장 단순한 GET 하나를 골라 <code>server.py → 라우터 → 서비스 → 리포지토리 → models/db</code>
          순서로 따라가 보세요. 여기서 본 것의 "큰 버전" 이에요.
        </p>
      </Explain>
    </div>
  )
}
