# 5주차 — 테스트 + 타입체크 + 시드

> 목표: 지금까지 손으로 확인하던 것을 자동화한다. 코드를 고쳐도 "아직 다 되는지" 를 5초 만에 알 수 있게.
> 결과물: pytest 69개 통과, basedpyright strict 에러 0, 한 번에 샘플 데이터를 넣는 seed 스크립트.

## 만든 것

```
tests/
├── conftest.py          # 공용 fixture: 테스트 DB, 클라이언트, 역할별 사용자
├── test_health.py       # 공개 경로
├── test_auth.py         # 가입·로그인·쿠키·토큰 검증·미들웨어
├── test_tickets.py      # CRUD·검증·페이지네이션·상태 전이·감사 로그
├── test_rbac.py         # 역할 4종 × 행위 매트릭스
└── test_ticket_repo.py  # 리포지토리 단위 테스트 (pytest-asyncio)
app/
├── core/clock.py        # utcnow(): 밀리초로 자른 UTC 시각
└── scripts/seed.py      # 샘플 사용자 5명 + 티켓 5개 (+ 감사 로그)
pyproject.toml           # [tool.pytest.ini_options], [tool.basedpyright]
```

```bash
uv run pytest                      # 테스트
uv run basedpyright                # 타입 검사
uv run python -m app.scripts.seed  # 샘플 데이터
```

## 핵심 개념

### 1. fixture = 테스트용 Depends

```python
@pytest.fixture(scope="session")
def writer(client: httpx.Client, admin: Actor) -> Actor: ...

def test_me_with_cookie(client: httpx.Client, writer: Actor) -> None:
    r = client.get("/auth/me", headers=writer.headers)
```

- 테스트 함수 인자에 이름을 적으면 pytest 가 그 fixture 를 실행해 넣어 준다. FastAPI `Depends` 와 같은 발상.
- fixture 가 fixture 를 받으면 체인이 된다:

```
sync_db ─ client ─ admin ─┬─ writer
                          ├─ reader
                          ├─ owner
                          └─ owner_other
```

- `writer` 하나를 달라고 하면 DB 정리 → 서버 기동 → admin 가입·로그인 → writer 가입 → admin 이 역할 부여 → writer 로그인이 자동으로 조립된다.

### 2. scope — 언제 다시 만드나

| scope | 의미 | 쓴 곳 |
| --- | --- | --- |
| `session` | 전체 실행 중 1회 | DB 연결, 클라이언트, 사용자 5명 (bcrypt 가 느려서) |
| `function` (기본) | 테스트마다 | 티켓·감사로그 비우기 |

- `autouse=True`: 아무도 안 불러도 항상 실행. 컬렉션 비우기와 **admin fixture** 에 붙였다.
  (admin 에 붙인 이유: 어떤 테스트가 먼저 돌든 "첫 가입자 = ADMIN" 자리를 fixture 가 차지해야 한다. 안 그러면 test_auth 의 임의 가입이 ADMIN 이 된다 — 실제로 한 번 당했다.)

### 3. 테스트 DB 분리 + 안전장치

```python
os.environ["MONGO_DB_NAME"] = "ticket_api_test"   # app import 보다 먼저!
...
assert settings.mongo_db_name == "ticket_api_test", "테스트가 실제 DB 를 가리키고 있다!"
```

- 환경변수 > `.env` 우선순위를 이용. 세션 시작·종료 시 DB 통째로 drop.
- 실수로 실제 DB 를 지우지 않도록 fixture 와 `test_health` 두 군데서 DB 이름을 확인한다.
- 정리 작업은 **동기** `MongoClient` 로 — TestClient 의 이벤트 루프와 섞이지 않는다.

### 4. TestClient 는 하나, 사용자는 쿠키 헤더로

```python
@dataclass(frozen=True)
class Actor:
    email: str; id: str; role: str
    headers: dict[str, str]        # {"Cookie": "access_token=..."}

client.get("/tickets", headers=writer.headers)
```

- TestClient 를 여러 개 만들면 앱의 Mongo 클라이언트가 다른 루프에 묶여 깨진다 (4주차 삽질).
- 클라이언트 전역 쿠키 저장소는 비워 두고, 사용자별 쿠키를 `Actor` 에 들고 다닌다.

### 5. parametrize — 규칙은 표로

```python
@pytest.mark.parametrize(("who", "group", "expected"), [
    ("admin", "anything", 201),
    ("writer", "mobile", 403),
    ("reader", "backend", 403),
])
def test_create_permissions(client, actors, who, group, expected): ...
```

- 테스트 하나 + 표 = 행 수만큼 테스트. Vitest `it.each`.
- 권한 매트릭스처럼 조합이 많은 규칙은 표로 적으면 **규칙 자체가 리뷰 대상**이 된다.

### 6. 테스트가 찾아낸 버그 두 개

**(a) naive vs aware datetime**

```
TypeError: can't compare offset-naive and offset-aware datetimes
```

- Mongo 는 시간대 없는 UTC 로 저장. 우리가 넣은 `datetime.now(UTC)` 는 시간대 있음. 읽어오면 시간대가 빠져 비교가 터진다.
- 해결: `AsyncMongoClient(..., tz_aware=True)` — 읽을 때 UTC 를 붙여 준다.

**(b) 밀리초 정밀도 (간헐 실패)**

```
assert 01:41:43.437000+00:00 > 01:41:43.437318+00:00   ← DB 에서 읽은 값이 메모리 값보다 '과거'
```

- Mongo 는 밀리초까지만 저장. 메모리의 마이크로초 값과 DB 왕복 값이 달라 4번 중 2번 실패.
- 해결: `core/clock.py` 의 `utcnow()` 가 처음부터 밀리초로 잘라서 "넣은 값 == 읽은 값" 보장. 모든 리포지토리가 이것만 쓴다.
- 교훈: **간헐적으로 실패하는 테스트(flaky test)는 보통 테스트가 아니라 코드의 숨은 가정을 드러낸다.**

### 7. basedpyright strict

```toml
[tool.basedpyright]
typeCheckingMode = "strict"
include = ["app", "tests"]
```

처음 300개 에러. 원인은 몇 가지뿐이었다:

| 원인 | 수 | 해결 |
| --- | --- | --- |
| pymongo 제네릭 미지정 (`AsyncDatabase` → `Unknown` 전파) | 대부분 | `Document = dict[str, Any]`, `MongoDB = AsyncDatabase[Document]` 별칭을 `core/db.py` 에 두고 전부 그걸로 |
| starlette 1.10 이 타입 검사 시 `httpx2` 를 기대 → `TestClient` 가 Unknown | 테스트 전부 | 테스트 타입을 `httpx.Client` 로 (TestClient 는 그 하위 클래스) + `cast` 1곳 |
| `asynccontextmanager` + `AsyncIterator` 반환 deprecated | 1 | `AsyncGenerator[None]` |
| PyJWT `encode/decode` 인자 타입 느슨 | 2 | 그 줄에만 `# pyright: ignore[reportUnknownMemberType]` |

- TS strict 와 체감이 비슷하다: **Unknown 을 허용하지 않는다** (`Any` 는 허용). 라이브러리 경계에서만 좁게 ignore.
- 제네릭 별칭 하나로 80개가 사라진 것처럼, 에러 수보다 **원인 수**를 세는 게 중요하다.

### 8. seed 스크립트

```python
tickets = TicketService(TicketRepository(db), AuditService(AuditRepository(db)))
t1 = await tickets.create(owner1, {...})
await tickets.approve(writer, t1.id)      # 권한 규칙 그대로, 감사 로그 그대로
```

- 리포지토리에 직접 넣지 않고 **서비스를 통해** 넣는다 → 실제 사용과 같은 데이터(감사 로그 포함).
- 멱등(idempotent): 사용자는 upsert, 시드 사용자의 티켓·로그는 지우고 다시 만든다. 몇 번 돌려도 같은 상태.
- `APP_ENV` 가 dev/test 가 아니면 거부 — 운영 DB 사고 방지.

## 용어 정리

| 용어 | 뜻 | 프론트 대응 |
| --- | --- | --- |
| fixture | 테스트에 주입되는 준비물 (DB, 클라이언트, 사용자) | `beforeEach` + 반환값, RTL `render` |
| scope | fixture 생명주기 (session / module / function) | — |
| autouse | 안 불러도 항상 실행되는 fixture | 전역 `beforeEach` |
| parametrize | 같은 테스트를 여러 입력으로 | `it.each` |
| conftest.py | 폴더 전체가 공유하는 fixture 파일 | `setupTests.ts` |
| flaky test | 코드 변경 없이 가끔 실패하는 테스트 | — |
| 멱등 (idempotent) | 여러 번 실행해도 결과가 같음 | — |
| tz-aware / naive | 시간대 정보가 있는 / 없는 datetime | `Date` 는 항상 UTC 기반 |
| strict 모드 | Unknown 타입을 에러로 | `tsconfig strict` |
| 제네릭 별칭 | `MongoDB = AsyncDatabase[Document]` | `type Db = Database<Doc>` |

## 삽질 기록

- 테스트 순서 때문에 엉뚱한 사용자가 ADMIN 이 됨 → admin fixture `autouse`.
- `TestClient` 가 strict 에서 Unknown → starlette 가 `httpx2` 를 기대. 설치는 권한 문제로 못 함. `httpx.Client` 로 타입 지정.
- 간헐 실패 → 밀리초 정밀도. `utcnow()` 로 통일.
- `jwt` 비밀키 30바이트 경고 → `JWT_SECRET` 32자 미만이면 시작 거부하도록 설정에 `Field(min_length=32)`. `.env` 도 교체.

## 회사 코드 읽을 때

- `tests/conftest.py` 부터 연다. fixture 체인을 보면 시스템이 무엇을 중요하게 여기는지(어떤 역할, 어떤 DB, 어떤 초기 데이터) 드러난다.
- `pyproject.toml` 의 `[tool.basedpyright]`/`[tool.pytest.ini_options]` 로 실행 규칙을 확인한다.
- 시드/마이그레이션 스크립트는 `scripts/` 에 있고, 서비스를 거치는지 DB 를 직접 만지는지 본다.
