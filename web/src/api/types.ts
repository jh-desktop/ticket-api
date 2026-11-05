// 백엔드 app/models/api/*.py 와 1:1 로 맞춘 타입. (Pydantic 모델 ↔ TS 타입)

export type Role = 'ADMIN' | 'GROUP_WRITER' | 'GROUP_READER' | 'OWNER'
export type TicketStatus = 'open' | 'approved' | 'rejected'

export interface User {
  id: string
  email: string
  role: Role
  groups: string[]
}

export interface Ticket {
  id: string
  title: string
  description: string | null
  status: TicketStatus
  owner_id: string
  group_id: string
  created_at: string
}

export type AuditAction =
  | 'ticket.created'
  | 'ticket.updated'
  | 'ticket.approved'
  | 'ticket.rejected'
  | 'ticket.deleted'

export interface AuditLog {
  id: string
  ticket_id: string
  action: AuditAction
  actor: string
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  created_at: string
}

export interface Snapshot {
  id: string
  taken_at: string
  total: number
  by_status: Record<string, number>
  by_group: Record<string, number>
}

export interface DocSummary {
  name: string
  title: string
}
export interface DocContent extends DocSummary {
  markdown: string
}

export interface GlossaryEntry {
  term: string
  meaning: string
  frontend: string
  source: string
}

export interface LayerInfo {
  key: string
  name: string
  folder: string
  role: string
  knows: string[]
  never: string[]
  company: string
  files: string[]
}
export interface FileInfo {
  path: string
  layer: string
  summary: string
  company: string
}
export interface Structure {
  layers: LayerInfo[]
  files: FileInfo[]
  request_flow: string[]
}

export interface ApiErrorBody {
  error?: { code: string; message: string }
  detail?: Array<{ loc: Array<string | number>; msg: string }> | string
}
