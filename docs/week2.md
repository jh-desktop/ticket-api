# 2주차 — MongoDB + 리포지토리 레이어

> 목표: 임시 dict 를 진짜 DB 로 바꾸고, DB 를 만지는 코드를 한 곳(리포지토리)에 가둔다.
> 결과물: 서버를 껐다 켜도 남아 있는 티켓 CRUD API.

## 만든 것

```
app/
├── core/db.py                  # Mongo 연결 1개 생성·종료, get_db 의존성
├── models/db/tickets.py        # DB 에 저장된 모양 (TicketDoc)
├── repositories/ticket_repo.py # tickets 컬렉션 쿼리 전부
└── server.py                   # lifespan: 시작 시 연결 + 인덱스, 종료 시 해제
docker-compose.yml              # 로컬 MongoDB 컨테이너
```

## 요청 흐름 (1주차와 달라진 부분)

```
라우터 create_ticket(body, repo)
    │  repo 는 Depends 체인으로 들어옴: get_db → get_ticket_repo → 라우터
    ▼
TicketRepository.create(data)
    │  insert_one → Mongo
    ▼
TicketDoc (DB 모델, _id 는 ObjectId → str)
    │  response_model=TicketResponse 로 걸러서
    ▼
201 {"id": "6ae0...", "title": ..., "status": "open", "created_at": ...}
```

## 핵심 개념

### 1. 환경: Docker → WSL → MongoDB

```
MongoDB 컨테이너 (ticket-api-mongo)
   ↑ Docker Desktop 이 만들고 관리
   ↑ WSL (Windows 안의 작은 Linux) 위에서 돌아감
```

- `docker compose up -d` / `down` 으로 켜고 끈다. 데이터는 `mongo_data` 볼륨에 남는다.
- Compass (`mongodb://localhost:27017`) 로 데이터를 눈으로 본다.
- 왜 Docker 인가: 삭제가 깨끗하고, 버전 바꾸기 쉽고, 회사 배포 형태(K8s)와 같다.

### 2. `async` / `await`

- JS 와 같다. DB 호출처럼 기다리는 작업 앞에 `await`.
- **`await` 는 `async def` 안에서만.** DB 를 만지는 함수는 전부 `async def` 가 된다.
- 주의: `async def` 안에서 동기(블로킹) 함수를 부르면 서버 전체가 멈춘다 (Node 이벤트루프와 같은 이유).

### 3. `lifespan` — 서버의 시작과 끝

```python
@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect_db()                                   # 시작 직후
    await TicketRepository(get_db()).ensure_indexes()    # 인덱스 보장
    yield                                                # ← 여기서 요청 처리
    await close_db()                                     # 종료 직전

app = FastAPI(lifespan=lifespan)
```

- `yield` 가 경계. React `useEffect` 의 마운트 / 언마운트 cleanup 과 같은 역할.
- Mongo 가 꺼져 있으면 서버가 아예 안 뜬다 → "DB 없이 떠서 나중에 터지는" 상황 방지.

### 4. `core/db.py` — 연결은 하나만

```python
class _Mongo:
    client: AsyncMongoClient | None = None
    db: AsyncDatabase | None = None

def get_db() -> AsyncDatabase: ...   # Depends(get_db) 로 받아 씀
```

- 앱 전체에서 연결 객체 1개를 돌려 쓴다 (axios 인스턴스 하나 만들어 import 하는 것과 같은 이유).
- 용어: **client** = Mongo 서버와의 연결, **database** = `client["ticket_api"]`, **collection** = `db["tickets"]` (테이블에 해당).

### 5. 리포지토리 — Mongo 문법을 가두는 곳

```python
class TicketRepository:
    def __init__(self, db: AsyncDatabase):
        self._col = db["tickets"]

    async def get(self, ticket_id: ObjectId) -> TicketDoc | None:
        doc = await self._col.find_one({"_id": ticket_id})
        return TicketDoc.model_validate(doc) if doc else None
```

| Mongo 명령 | 뜻 |
| --- | --- |
| `insert_one(doc)` | 문서 1건 추가. `result.inserted_id` 로 id 받음 |
| `find_one({"_id": id})` | 1건 조회. 없으면 `None` |
| `find().sort().skip().limit()` | 여러 건. **커서**를 돌려주므로 `async for` 로 꺼냄 |
| `find_one_and_update(filter, {"$set": {...}}, return_document=True)` | 수정하고 바뀐 문서 반환 |
| `delete_one({"_id": id})` | 삭제. `deleted_count` 로 성공 여부 |
| `create_index([("status", 1)])` | 인덱스. 이미 있으면 무시 |

- 라우터는 `repo.get(id)` 같은 파이썬 메서드만 부른다. Mongo 문법은 이 파일 밖으로 안 나간다.
- 프론트에서 `fetch` 를 `api/tickets.ts` 에 모으고 컴포넌트는 `getTicket(id)` 만 부르는 구조와 같다.

### 6. `ObjectId`

- Mongo 가 자동으로 붙이는 24자리 16진수 id. Python 에선 `ObjectId` 객체, JSON 에선 문자열.
- **들어올 때** (라우터): `ObjectId.is_valid(s)` 확인 후 `ObjectId(s)`. 형식이 틀리면 404.
- **나갈 때** (DB 모델): `ObjectIdStr = Annotated[str, BeforeValidator(str)]` — 검증 전에 `str()` 을 거쳐 문자열로.
- Mongo 는 id 를 `_id` 로 저장 → `id: ObjectIdStr = Field(alias="_id")` 로 파이썬에선 `.id` 로 부름.

### 7. DB 모델 vs API 모델

| | `TicketDoc` (models/db) | `TicketResponse` (models/api) |
| --- | --- | --- |
| 역할 | DB 에 저장된 모양 그대로 | 프론트에 보여줄 것만 |
| `updated_at` | 있음 | 없음 |
| `_id` alias | 있음 | 없음 (`id: str`) |

- `response_model=TicketResponse` 가 필터 역할. 4주차에 `users` 에 비밀번호 해시가 생기면 이 분리가 왜 필요한지 바로 보인다.

### 8. 의존성 체인 + 타입 별칭

```python
def get_ticket_repo(db: Annotated[AsyncDatabase, Depends(get_db)]) -> TicketRepository:
    return TicketRepository(db)

TicketRepo = Annotated[TicketRepository, Depends(get_ticket_repo)]   # 라우터에서 repo: TicketRepo
```

- 의존성이 의존성을 가진다: `get_db → get_ticket_repo → 라우터`. 회사는 `→ get_service →` 가 한 단계 더 있다 (3주차).

### 9. 페이지네이션

```python
skip: Annotated[int, Query(ge=0)] = 0
limit: Annotated[int, Query(ge=1, le=100)] = 20
```

- `?skip=20&limit=20` 으로 2페이지. `Query(ge=, le=)` 로 범위 검증 → `limit=1000` 은 422.

## 용어 정리

| 용어 | 뜻 | 프론트 대응 |
| --- | --- | --- |
| 컨테이너 | 격리된 상자 안에서 도는 프로그램 1개 | — |
| 이미지 | 컨테이너의 설계도 (`mongo:7`) | npm 패키지 |
| 볼륨 | 컨테이너 밖에 두는 데이터 저장소 | — |
| 컬렉션 / 문서 | 테이블 / 행(row). Mongo 는 스키마 없이 JSON 비슷한 문서를 저장 | — |
| 커서 | 조회 결과를 한 건씩 꺼내는 손잡이 | 이터레이터 / 제너레이터 |
| 인덱스 | 자주 검색하는 필드의 색인. 없어도 동작, 있으면 빠름 | — |
| lifespan | 서버 시작/종료 훅 | `useEffect` 마운트/언마운트 |
| ObjectId | Mongo 의 자동 id | — |

## 삽질 기록

- Docker Desktop 설치 후 엔진이 안 뜸 → **WSL 미설치**. 관리자 PowerShell 에서 `wsl --install --no-distribution` + 재부팅.
- 재부팅 후 `docker` 가 파이프를 못 찾음 → Docker Desktop 앱을 다시 안 켠 것. 설정에서 로그인 시 자동 시작 켜두기.
- 새 터미널 명령을 못 찾음 (uv, docker 공통) → 설치 후 VS Code 를 완전히 재시작해야 PATH 반영.

## 아직 회사 구조와 다른 점 (3주차에 고침)

- 라우터가 리포지토리를 직접 부름 → 라우터 → **서비스** → 리포지토리로 한 단계 추가
- 에러를 라우터마다 `HTTPException` 으로 던짐 → 커스텀 예외 + 핸들러로 통일
- 상태 전이 규칙 없음 (아무 때나 아무 상태로) → 서비스에서 `open → approved | rejected` 만 허용
- 변경 기록 없음 → 감사 로그
