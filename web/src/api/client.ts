import type { ApiErrorBody } from './types'

/** 요청 한 번의 기록. 설명 패널(TracePanel)이 이걸 그린다. */
export interface ApiCall {
  id: number
  at: Date
  method: string
  path: string
  requestBody: unknown
  status: number
  ok: boolean
  clientMs: number
  serverMs: number | null
  requestId: string | null
  /** 백엔드 X-Trace 헤더: 이 요청이 지난 지점들 ("service:TicketService.approve" …) */
  trace: string[]
  responseBody: unknown
}

export class ApiError extends Error {
  status: number
  code: string
  call: ApiCall
  constructor(status: number, code: string, message: string, call: ApiCall) {
    super(message)
    this.status = status
    this.code = code
    this.call = call
  }
}

type Listener = (call: ApiCall) => void
const listeners = new Set<Listener>()
let seq = 0

/** 모든 API 호출을 구독한다. (CallsProvider 가 사용) */
export function onApiCall(fn: Listener): () => void {
  listeners.add(fn)
  return () => {
    listeners.delete(fn)
  }
}

function parseTrace(header: string | null): string[] {
  if (!header) return []
  try {
    const v: unknown = JSON.parse(header)
    return Array.isArray(v) ? v.filter((s): s is string => typeof s === 'string') : []
  } catch {
    return []
  }
}

function errorMessage(body: ApiErrorBody | null, fallback: string): { code: string; message: string } {
  if (body?.error) return body.error
  if (Array.isArray(body?.detail)) {
    const first = body.detail[0]
    const field = first?.loc?.slice(-1)[0]
    return { code: 'validation_error', message: `${String(field ?? '')}: ${first?.msg ?? '입력값 오류'}` }
  }
  if (typeof body?.detail === 'string') return { code: 'http_error', message: body.detail }
  return { code: 'http_error', message: fallback }
}

/**
 * fetch 한 겹 감싼 것. 하는 일:
 *  1. /api 접두사 (Vite 프록시 → 백엔드)
 *  2. credentials: 'include' — 쿠키를 보내고 받는다. 이 한 줄이 없으면 로그인이 "되는 것 같은데" 다음 요청부터 401 이 난다.
 *  3. 응답 헤더 X-Trace / X-Duration-Ms 를 읽어 ApiCall 로 기록
 *  4. 실패(4xx/5xx)면 ApiError 로 던진다 → 화면은 code/message 로 분기
 */
export async function api<T>(method: string, path: string, body?: unknown): Promise<T> {
  const started = performance.now()
  const res = await fetch(`/api${path}`, {
    method,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: 'include',
  })
  const text = await res.text()
  let data: unknown = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = text
  }
  const serverMs = res.headers.get('x-duration-ms')
  const call: ApiCall = {
    id: ++seq,
    at: new Date(),
    method,
    path,
    requestBody: body,
    status: res.status,
    ok: res.ok,
    clientMs: Math.round(performance.now() - started),
    serverMs: serverMs ? Number(serverMs) : null,
    requestId: res.headers.get('x-request-id'),
    trace: parseTrace(res.headers.get('x-trace')),
    responseBody: data,
  }
  listeners.forEach((l) => l(call))
  if (!res.ok) {
    const { code, message } = errorMessage(data as ApiErrorBody | null, res.statusText)
    throw new ApiError(res.status, code, message, call)
  }
  return data as T
}

export const get = <T>(path: string) => api<T>('GET', path)
export const post = <T>(path: string, body?: unknown) => api<T>('POST', path, body)
export const patch = <T>(path: string, body?: unknown) => api<T>('PATCH', path, body)
export const del = <T>(path: string) => api<T>('DELETE', path)
