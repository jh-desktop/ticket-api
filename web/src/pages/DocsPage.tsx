import { useEffect, useState } from 'react'
import Markdown from 'react-markdown'
import { useParams, Link } from 'react-router-dom'
import remarkGfm from 'remark-gfm'

import { get } from '../api/client'
import type { DocContent, DocSummary } from '../api/types'

export function DocsPage() {
  const { name } = useParams()
  const [list, setList] = useState<DocSummary[]>([])
  const [doc, setDoc] = useState<DocContent | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    get<DocSummary[]>('/learn/docs').then(setList).catch((e: Error) => setErr(e.message))
  }, [])

  useEffect(() => {
    const target = name ?? 'week1'
    setDoc(null)
    get<DocContent>(`/learn/docs/${target}`).then(setDoc).catch((e: Error) => setErr(e.message))
  }, [name])

  return (
    <div className="page docs">
      <h1>학습 노트</h1>
      <p className="lead">6주 동안 만들면서 쓴 정리예요. 레포의 <code>docs/week*.md</code> 를 그대로 보여줘요.</p>
      <div className="doc-tabs">
        {list.map((d) => (
          <Link key={d.name} to={`/docs/${d.name}`} className={(name ?? 'week1') === d.name ? 'on' : ''}>
            {d.title.split('—')[0]?.trim() ?? d.name}
          </Link>
        ))}
      </div>
      {err && <p className="errorline">{err}</p>}
      {!doc && !err && <p className="muted">불러오는 중…</p>}
      {doc && (
        <article className="markdown">
          <Markdown remarkPlugins={[remarkGfm]}>{doc.markdown}</Markdown>
        </article>
      )}
    </div>
  )
}
