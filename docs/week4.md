# 4주차 — JWT 인증 + RBAC

> 목표: "누구인가(인증)" 와 "무엇을 할 수 있나(인가)" 를 분리해서 붙인다.
> 결과물: 쿠키 기반 로그인, 역할 4종 + 그룹 스코핑, 모든 요청이 지나는 인증 관문.

## 만든 것

```
app/
├── core/
│   ├── security.py      # 비밀번호 해싱 (bcrypt)
│   ├── auth.py          # JWT 발급·검증, 쿠키 심기/지우기, get_current_user
│   └── rbac.py          # 역할·그룹 규칙 전부
├── models/db/users.py   # UserDoc (password_hash 포함 — 응답으로 절대 안 나감)
├── models/api/
│   ├── auth_api.py      # SignupRequest, LoginRequest, UserResponse
│   └── user_api.py      # UserRoleUpdate
├── repositories/user_repo.py
├── services/
│   ├── auth_service.py  # signup / login
│   └── user_service.py  # 역할 부여 (ADMIN 용)
├── api/v1/
│   ├── auth_router.py   # signup, login, logout, me
│   └── user_router.py   # GET /users, PATCH /users/{id}/role
└── server.py            # auth_middleware + _NO_AUTH_PATHS
```

| 메서드 | 경로 | 하는 일 | 누가 |
| --- | --- | --- | --- |
| POST | `/auth/signup` | 가입. 첫 가입자는 ADMIN | 누구나 |
| POST | `/auth/login` | 검증 후 `Set-Cookie: access_token` | 누구나 |
| POST | `/auth/logout` | 쿠키 삭제 | 누구나 |
| GET | `/auth/me` | 쿠키가 가리키는 나 | 로그인 |
| GET | `/users` | 사용자 목록 | ADMIN |
| PATCH | `/users/{id}/role` | 역할·그룹 부여 | ADMIN |

## 요청 흐름 (인증·인가가 끼어드는 자리)

```
POST /tickets/{id}/approve  (Cookie: access_token=...)
    │
    ▼
① auth_middleware (server.py)
    │  _NO_AUTH_PATHS 면 통과. 아니면 토큰 존재 + 서명 + 만료만 확인. 틀리면 401 끝.
    ▼
② Depends(require_role("ADMIN","GROUP_WRITER"))  (라우터 입구)
    │  → Depends(get_current_user): 토큰의 sub 로 DB 에서 사용자 조회
    │  역할이 아니면 403 끝.
    ▼
③ TicketService.approve(actor, ticket_id)
    │  get: 못 보는 티켓이면 404
    │  rbac.can_transition(actor, ticket): 그 그룹의 WRITER 가 아니면 403
    │  전이 규칙 → repo.update → audit.record(actor=actor.id)
    ▼
200
```

세 겹이다. 미들웨어는 "토큰이 멀쩡한가", `get_current_user` 는 "누구인가", 서비스는 "이 티켓에 이걸 해도 되나".

## 핵심 개념

### 1. 비밀번호는 해시만 저장

```python
hash_password(plain)            # bcrypt.hashpw(plain, gensalt())  — 매번 다른 해시
verify_password(plain, hashed)  # bcrypt.checkpw
```

- 한 방향. DB 가 털려도 비밀번호는 안 샌다.
- 로그인 실패 메시지는 "이메일 없음" 과 "비밀번호 틀림" 을 **같게** — 가입 여부를 흘리지 않는다.
- 이메일 unique 인덱스: 서비스에서 확인해도 동시 요청은 뚫릴 수 있으니 DB 가 마지막 방어선.

### 2. JWT = 서명된 신분증

```
payload: {"sub": user_id, "role": "OWNER", "groups": [...], "iat": ..., "exp": ...}
token = jwt.encode(payload, JWT_SECRET, "HS256")
```

- 서버가 세션을 저장하지 않는다. 토큰 안에 누구·무슨 역할이 있고, 서명으로 위조를 막는다.
- **서명이지 암호화가 아니다.** payload 는 누구나 읽는다. 비밀번호 같은 건 절대 넣지 않는다.
- `JWT_SECRET` 이 새면 누구나 ADMIN 토큰을 만들 수 있다 → `.env` 에만.
- 만료(`exp`) 와 위조(다른 비밀키) 는 `jwt.decode` 가 잡는다.

### 3. 토큰은 HttpOnly 쿠키로 (회사 방식)

```python
response.set_cookie(key="access_token", value=token,
                    httponly=True,   # JS 에서 못 읽음 → XSS 로 탈취 방지
                    secure=settings.cookie_secure,  # 운영(https)만 True
                    samesite="lax",  # 다른 사이트발 요청엔 안 붙음 → CSRF 완화
                    max_age=...)
```

| | 헤더 방식 | 쿠키 방식 (우리/회사) |
| --- | --- | --- |
| 프론트가 할 일 | 토큰 저장 + 매 요청 `Authorization` 헤더 | 없음 (`credentials: "include"` 만) |
| 서버가 꺼내는 곳 | `Authorization: Bearer` | `request.cookies["access_token"]` |
| XSS 에 | 취약 (localStorage 읽힘) | 안전 (HttpOnly) |

- 발급·검증 코드는 동일. **꺼내는 곳만** 다르다 (`extract_token`: 쿠키 우선, Bearer 헤더 폴백).
- 로그인 응답 본문엔 토큰이 없고 사용자 정보만. 앱 시작 시 `GET /auth/me` 로 로그인 상태 확인.
- `request: Request` / `response: Response` 를 인자로 선언하면 FastAPI 가 이번 요청/응답 객체를 넣어 준다.

### 4. `get_current_user` — "지금 요청한 사람"

```python
async def get_current_user(request: Request, settings: ..., users: ...) -> UserDoc:
    token = extract_token(request)          # 쿠키/헤더
    payload = decode_access_token(token)    # 서명·만료
    return await users.get(ObjectId(payload["sub"]))   # DB 조회

CurrentUser = Annotated[UserDoc, Depends(get_current_user)]
```

- 라우터에서 `user: CurrentUser` 한 줄. 토큰이 틀리면 라우터 본문은 실행조차 안 된다.
- 1주차 `settings: Annotated[Settings, Depends(get_settings)]` 와 같은 모양. 회사 코드의 `Depends(get_current_user)` 가 이것.

### 5. RBAC — 역할 4종

| 역할 | 조회 | 생성 | 수정·삭제 | 승인·반려 |
| --- | --- | --- | --- | --- |
| ADMIN | 전부 | 어디든 | 전부 | 전부 |
| GROUP_WRITER | 내 그룹 | 내 그룹 | 내 것 | 내 그룹 |
| GROUP_READER | 내 그룹 | ✗ | ✗ | ✗ |
| OWNER | 내 것 | 내 그룹 | 내 것 | ✗ |

규칙은 `core/rbac.py` 한 파일에만 있다. 두 가지 형태로 쓰인다:

**(a) 조회는 필터로**

```python
def scope_filter(user) -> dict:
    ADMIN → {}
    GROUP_* → {"group_id": {"$in": user.groups}}
    OWNER → {"owner_id": user.id}
```

"권한 없음" 응답이 아니라 Mongo 쿼리에 섞여서 **볼 수 있는 것만 나온다**. 인가 결과가 허용/거부가 아니라 쿼리 조건.

**(b) 행위는 True/False 로**

```python
can_view / can_create / can_edit / can_transition (user, ticket) -> bool
ensure(allowed, message)   # False 면 ForbiddenError(403)
```

### 6. 404 vs 403

- 볼 수 없는 티켓 → **404**. 403 이라 하면 "그 id 가 존재한다" 가 샌다. 없는 척한다.
- 볼 수는 있지만 할 수 없는 행위 → **403**.
- 서비스의 `get(actor, id)` 가 "없거나 못 보면 404" 를 한 번에 처리 → 나머지 메서드는 `get` 뒤에 `ensure(can_xxx)` 만 붙인다.

### 7. 두 단계 검사: 입구와 내부

```python
Approver = Annotated[UserDoc, Depends(require_role("ADMIN", "GROUP_WRITER"))]

async def approve_ticket(ticket_id: str, user: Approver, svc: Service): ...
```

- `require_role`: 역할 자체가 안 되는 요청을 라우터 입구에서 403. "어느 그룹인가" 는 모른다.
- `can_transition`: 서비스가 티켓을 꺼내 본 뒤 "그 그룹의 WRITER 인가" 판단.
- `_: Admin` — 값은 안 쓰지만 선언만으로 검사가 강제된다.

### 8. 미들웨어 + `_NO_AUTH_PATHS` (회사 `server.py` 와 같은 구조)

```python
_NO_AUTH_PATHS = {"/health", "/docs", "/openapi.json", "/auth/signup", "/auth/login", "/auth/logout"}
_NO_AUTH_PREFIXES = ("/scheduler/",)   # 6주차: K8s CronJob 호출

@app.middleware("http")
async def auth_middleware(request, call_next):
    if path in _NO_AUTH_PATHS or path.startswith(_NO_AUTH_PREFIXES): return await call_next(request)
    token = extract_token(request) → 없으면 401
    decode_access_token(token) → 만료/위조면 401
    return await call_next(request)
```

- `Depends` 만으로도 인증은 되지만, "모든 요청이 지나는 관문" 을 하나 두면 **인증을 깜빡한 라우터가 생겨도** 토큰 없는 요청은 못 들어온다. 안전망.
- 미들웨어는 토큰의 형식·서명·만료만 본다. DB 조회(누구인가)와 RBAC 은 안 한다 — 그건 `get_current_user` 와 서비스의 일.
- 미들웨어에서 `raise` 한 예외는 `exception_handler` 를 거치지 않는다 → `error_response()` 로 직접 응답을 만든다.
- 미들웨어가 라우팅보다 먼저라, 없는 경로도 토큰 없으면 404 가 아니라 401.

### 9. 부트스트랩

- 가입하면 전부 OWNER, `groups=[]`. 첫 가입자만 ADMIN (`users.count() == 0`).
- ADMIN 이 `PATCH /users/{id}/role` 로 `{"role": "GROUP_WRITER", "groups": ["backend"]}` 부여.

## React 에서 달라지는 것

```js
await fetch("/auth/login", { method: "POST", headers: {"Content-Type": "application/json"},
                             body: JSON.stringify({ email, password }), credentials: "include" });
await fetch("/tickets", { credentials: "include" });   // 토큰 코드 없음
```

- 토큰을 저장하거나 헤더에 붙이는 코드가 사라진다. 앱 시작 시 `GET /auth/me` 한 번.
- 프론트·백 도메인이 다르면 CORS 에 `allow_credentials=True` 필요.

## 용어 정리

| 용어 | 뜻 | 프론트 대응 |
| --- | --- | --- |
| 인증 (authentication) | 누구인가 | 로그인 |
| 인가 (authorization) | 무엇을 할 수 있나 | 권한별 UI 노출 |
| 해시 / salt | 한 방향 변환 / 매번 다른 결과를 내는 무작위 값 | — |
| JWT / claim | 서명된 토큰 / 그 안의 필드 (`sub`, `exp`, `role`) | — |
| HttpOnly / SameSite | JS 접근 차단 / 교차 사이트 전송 제한 | 쿠키 옵션 |
| XSS / CSRF | 스크립트 주입 / 다른 사이트에서 몰래 요청 | — |
| RBAC | 역할 기반 접근 제어 | — |
| 스코핑 | 역할 + 소속(그룹)으로 범위를 좁힘 | — |
| 미들웨어 | 모든 요청이 지나는 공통 처리 | Express 미들웨어 |
| 401 / 403 | 누군지 모름 / 알지만 권한 없음 | — |

## 삽질 기록

- Compass 에서 `status` 를 아무 값으로 바꿨더니 `GET /tickets` 가 500 → `Literal` 검증. **DB 를 직접 고치면 Pydantic 을 건너뛴다.** 운영 DB 손대지 않기.
- 클래스 안의 `def list(...)` 가 그 아래 `list[str]` 타입 힌트를 가림 (`'function' object is not subscriptable`). `from __future__ import annotations` 로 해결. TS 엔 없는 함정.
- 테스트에서 `TestClient` 를 여러 개 만들면 Mongo 클라이언트가 다른 이벤트 루프에 묶여 에러. 클라이언트 하나 + 사용자별 쿠키 헤더로.
- 기존 티켓에 `owner_id`/`group_id` 가 없어 스키마 변경 후 조회 실패 → 마이그레이션(`updateMany`) 필요. 운영에선 스크립트로.

## 회사 코드 읽을 때 대응

| 미니 프로젝트 | 회사 레포 |
| --- | --- |
| `core/auth.py` `get_current_user`, `set_auth_cookie` | `drms/core/auth.py` |
| `core/rbac.py` `scope_filter`, `require_role` | `drms/core/rbac.py` |
| `server.py` `auth_middleware`, `_NO_AUTH_PATHS` | `drms/server.py` |
| `Role = Literal["ADMIN", "GROUP_WRITER", ...]` | 같은 4종 |
