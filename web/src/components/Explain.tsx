import type { ReactNode } from 'react'

/** 페이지 오른쪽에 붙는 설명 박스. 제목 + 본문. */
export function Explain({ title, children }: { title: string; children: ReactNode }) {
  return (
    <details className="explain" open>
      <summary>{title}</summary>
      <div className="explain-body">{children}</div>
    </details>
  )
}

/** 실패 메시지 표시용. ApiError 의 status/code/message 를 한 줄로. */
export function ErrorLine({ error }: { error: { status?: number; code?: string; message: string } | null }) {
  if (!error) return null
  return (
    <div className="errorline">
      {error.status && <span className="status warn">{error.status}</span>}
      {error.code && <code>{error.code}</code>}
      <span>{error.message}</span>
    </div>
  )
}
