# 3주차 — 서비스 레이어 + 에러 처리 + 감사 로그

> 목표: 라우터 → 서비스 → 리포지토리 3층 구조를 완성하고, 두 번째 도메인을 붙여 도메인 간 의존을 경험한다.
> 결과물: 승인/반려 상태 전이 + 모든 변경에 감사 로그 자동 기록.

## 만든 것

```
app/
├── core/exceptions.py           # AppError 계열 + 통일된 에러 응답 핸들러
├── services/
│   ├── ticket_service.py        # 상태 전이 규칙, 감사 서비스 호출
│   └── audit_service.py         # record() / list()
├── repositories/audit_repo.py   # insert / list 만 (수정·삭제 없음)
├── models/db/audit_logs.py      # AuditLogDoc, AuditAction
├── models/api/audit_api.py      # AuditLogResponse
└── api/v1/audit_router.py       # GET /audit-logs?ticket_id=
```

새 엔드포인트

| 메서드 | 경로 | 하는 일 | 응답 |
| --- | --- | --- | --- |
| POST | `/tickets/{id}/approve` | open → approved | 200 / 404 / 409 |
| POST | `/tickets/{id}/reject` | open → rejected | 200 / 404 / 409 |
| GET | `/audit-logs?ticket_id=` | 변경 이력 최신순 | 200 |

## 요청 흐름 (3층 완성)

```
POST /tickets/{id}/approve
    │
    ▼
라우터 approve_ticket(ticket_id, svc)         ── 받아서 넘기고 돌려줌. 판단 없음
    │
    ▼
TicketService.approve → _transition
    │  ① get → 없으면 NotFoundError
    │  ② _TRANSITIONS[현재상태] 에 "approved" 없으면 InvalidTransitionError
    │  ③ repo.update({"status": "approved"})
    │  ④ audit.record(before={"status":"open"}, after={"status":"approved"})
    ▼
TicketRepository.update / AuditRepository.insert   ── Mongo
    │
    ▼
예외가 튀어나오면 → exception_handler 가 {"error": {"code", "message"}} + 404/409 로 변환
```

## 핵심 개념

### 1. 3층의 책임

| 층 | 아는 것 | 모르는 것 | 코드 신호 |
| --- | --- | --- | --- |
| 라우터 `api/` | HTTP (상태코드, 요청 본문, 쿼리) | 규칙, DB | `@router.*`, `response_model`, `Query` |
| 서비스 `services/` | 규칙 ("되는 일인가") | HTTP, Mongo | `raise NotFoundError`, 전이 표 |
| 리포지토리 `repositories/` | Mongo 문법 | 규칙 | `find_one`, `$set`, `insert_one` |

"이 코드는 어느 층?" 판단 기준: HTTP 단어가 나오면 라우터, 할 수 있나 없나 규칙이면 서비스, Mongo 문법이면 리포지토리.

라우터는 전부 한 줄이 됐다:

```python
@router.post("/{ticket_id}/approve", response_model=TicketResponse)
async def approve_ticket(ticket_id: str, svc: Service):
    return await svc.approve(ticket_id)
```

### 2. 상태 전이 표

```python
_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    "open": {"approved", "rejected"},
    "approved": set(),      # 한 번 승인되면 끝
    "rejected": set(),
}
```

- 규칙을 `if` 여러 개로 흩뿌리지 않고 데이터 하나로. 규칙이 바뀌면 이 표만 고친다.
- `TicketStatus = Literal["open", "approved", "rejected"]` — TS 의 `"open" | "approved" | "rejected"`. 다른 값은 Pydantic 이 거부.

### 3. 커스텀 예외 + 핸들러

```python
class AppError(Exception):            # 부모. status_code 와 code 를 가진다
class NotFoundError(AppError):        status_code = 404; code = "not_found"
class InvalidTransitionError(AppError): status_code = 409; code = "invalid_transition"

@app.exception_handler(AppError)
async def _handle_app_error(_, exc):
    return JSONResponse(status_code=exc.status_code,
                        content={"error": {"code": exc.code, "message": exc.message}})
```

- 서비스는 `raise NotFoundError(...)` 만 한다. 그게 404 라는 건 핸들러가 안다. → 서비스가 HTTP 를 모르게 유지.
- 응답 모양 통일: `{"error": {"code", "message"}}`. 프론트에서 `error.code` 로 분기.
- 예외를 추가할 땐 클래스 하나만 더 만들면 된다. 핸들러는 그대로.
- Pydantic 검증 실패(422)는 FastAPI 기본 모양(`{"detail": [...]}`) 그대로 둠.

### 4. 도메인 하나 = 파일 한 벌

```
models/db/audit_logs.py  ──  models/db/tickets.py
models/api/audit_api.py  ──  models/api/ticket_api.py
repositories/audit_repo.py  ──  repositories/ticket_repo.py
services/audit_service.py  ──  services/ticket_service.py
api/v1/audit_router.py  ──  api/v1/ticket_router.py
```

회사 레포는 이 다섯 파일 패턴이 도메인 수만큼 반복된다. 하나를 읽을 줄 알면 나머지도 읽힌다.

### 5. 도메인 간 의존: 서비스 → 서비스

```python
class TicketService:
    def __init__(self, repo: TicketRepository, audit: AuditService): ...

    async def create(self, data):
        ticket = await self._repo.create(data)
        await self._audit.record(ticket_id=ticket.id, action="ticket.created", after=_snapshot(ticket))
        return ticket
```

- 티켓 서비스는 감사 **서비스**를 부른다. 감사 리포지토리를 직접 만지지 않는다 (층을 건너뛰지 않는다).
- 의존성 체인이 나무 모양이 됐다:

```
get_db ─┬─ get_ticket_repo ─────────────────────────┐
        └─ get_audit_repo ─ get_audit_service ─────┴─ get_ticket_service ─ 라우터
```

라우터는 여전히 `svc: Service` 하나만 받는다.

### 6. 감사 로그 설계

- **고치지 않는다**: `AuditRepository` 에 update/delete 가 없다. 메서드를 안 만들어 두면 코드로도 못 고친다.
- **바뀐 필드만**: 수정 로그는 `before={"description": "v1"}`, `after={"description": "v2"}`. 생성은 `before=None`, 삭제는 `after=None`.
- **실패한 시도는 안 남긴다**: 409 로 거부된 전이는 로그 없음. 실제로 바뀐 것만 기록.
- `actor` 는 지금 `"system"`. 4주차에 로그인 사용자 id 로 바뀐다.
- `action` 은 `"ticket.approved"` 처럼 "도메인.동사" 로.

### 7. 복합 인덱스 + 2차 정렬

```python
await self._col.create_index([("ticket_id", ASCENDING), ("created_at", DESCENDING)])
cursor = self._col.find(query).sort([("created_at", DESCENDING), ("_id", DESCENDING)])
```

- "이 티켓의 이력을 최신순으로" 가 가장 흔한 조회 → 그 조회에 맞춘 복합 인덱스.
- 같은 밀리초에 생긴 로그는 `created_at` 이 같아 순서가 섞인다 → `_id` 로 2차 정렬 (ObjectId 는 생성 순 증가).

## 용어 정리

| 용어 | 뜻 | 프론트 대응 |
| --- | --- | --- |
| 서비스 레이어 | 비즈니스 규칙이 사는 층 | 커스텀 훅 / 도메인 로직 모듈 |
| 상태 전이 | 상태 A 에서 B 로 가는 규칙 | 상태 머신, reducer 의 허용 액션 |
| 예외 핸들러 | 예외를 HTTP 응답으로 번역하는 함수 | Error Boundary |
| 409 Conflict | 요청은 올바르지만 현재 상태와 충돌 | — |
| 감사 로그 | 누가 언제 무엇을 바꿨는지의 기록 | — |
| 복합 인덱스 | 두 개 이상 필드를 묶은 인덱스 | — |
| `Literal` | 값을 몇 개로 고정하는 타입 | 문자열 리터럴 유니온 |
| `assert` | "여기선 이게 참이어야 함" 표시. 타입체커에게 None 아님을 알려줌 | TS `!` (non-null assertion) |

## 삽질 기록

- 감사 로그 순서가 뒤집힘 (created 가 updated 보다 아래) → 같은 밀리초 생성. `_id` 2차 정렬로 해결.
- Bash 로 긴 파일 여러 개를 한 번에 쓰다 따옴표 파싱 에러 → 파일별로 나눠 쓰는 게 안전.

## 아직 회사 구조와 다른 점 (4주차에 고침)

- 누구나 모든 티켓을 승인할 수 있음 → JWT 로그인 + 역할(RBAC) + 그룹 스코핑
- `actor = "system"` → 실제 사용자 id
- 인증 없는 경로 예외 목록(`_NO_AUTH_PATHS`) 없음 → 미들웨어
