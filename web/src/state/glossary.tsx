import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { get } from '../api/client'
import type { GlossaryEntry } from '../api/types'

interface GlossaryState {
  entries: GlossaryEntry[]
  byTerm: Map<string, GlossaryEntry>
}

const Ctx = createContext<GlossaryState>({ entries: [], byTerm: new Map() })

/** 용어집은 docs/week*.md 의 표에서 백엔드가 긁어 온다. 한 번만 받아서 전역에 둔다. */
export function GlossaryProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<GlossaryEntry[]>([])
  useEffect(() => {
    get<GlossaryEntry[]>('/learn/glossary')
      .then(setEntries)
      .catch(() => setEntries([]))
  }, [])
  const byTerm = useMemo(() => {
    const m = new Map<string, GlossaryEntry>()
    for (const e of entries) {
      // 같은 용어가 여러 주차에 있으면 처음 것(가장 기초 설명)을 쓴다
      const key = e.term.split(' / ')[0]?.trim().toLowerCase() ?? ''
      if (key && !m.has(key)) m.set(key, e)
    }
    return m
  }, [entries])
  return <Ctx.Provider value={{ entries, byTerm }}>{children}</Ctx.Provider>
}

export const useGlossary = () => useContext(Ctx)
