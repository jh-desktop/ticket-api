import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

import { onApiCall, type ApiCall } from '../api/client'

interface CallsState {
  calls: ApiCall[] // 최신이 앞
  selected: ApiCall | null
  select: (call: ApiCall | null) => void
}

const Ctx = createContext<CallsState | null>(null)
const MAX = 30

/** 앱 전체 API 호출 기록. 설명 패널이 "방금 그 요청" 을 보여주기 위해 쓴다. */
export function CallsProvider({ children }: { children: ReactNode }) {
  const [calls, setCalls] = useState<ApiCall[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)

  useEffect(
    () =>
      onApiCall((call) => {
        // /learn/* 은 설명 자료를 가져오는 호출이라 흐름 설명에선 숨긴다
        if (call.path.startsWith('/learn/')) return
        setCalls((prev) => [call, ...prev].slice(0, MAX))
        setSelectedId(null) // 새 요청이 오면 "최신" 을 따라간다
      }),
    [],
  )

  const selected = selectedId === null ? (calls[0] ?? null) : (calls.find((c) => c.id === selectedId) ?? null)
  return <Ctx.Provider value={{ calls, selected, select: (c) => setSelectedId(c?.id ?? null) }}>{children}</Ctx.Provider>
}

export function useCalls(): CallsState {
  const v = useContext(Ctx)
  if (!v) throw new Error('CallsProvider missing')
  return v
}
