import { Link } from 'react-router-dom'

import { useGlossary } from '../state/glossary'

/**
 * 본문 속 용어. 용어집에 있으면 점선 밑줄 + 마우스를 올리면 뜻이 뜬다. 클릭하면 용어집으로.
 *   <Term t="JWT" />          → 용어집의 "JWT" 설명
 *   <Term t="미들웨어">관문</Term> → 화면엔 "관문", 설명은 "미들웨어" 항목
 */
export function Term({ t, children }: { t: string; children?: React.ReactNode }) {
  const { byTerm } = useGlossary()
  const entry = byTerm.get(t.toLowerCase())
  if (!entry) return <>{children ?? t}</>
  const tip = entry.frontend ? `${entry.meaning}\n(프론트 대응: ${entry.frontend})` : entry.meaning
  return (
    <Link className="term" to={`/glossary?q=${encodeURIComponent(t)}`} title={tip}>
      {children ?? t}
    </Link>
  )
}
