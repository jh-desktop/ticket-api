# 1주차 — FastAPI + Pydantic + Depends

> 목표: 요청이 들어와서 응답이 나가기까지의 흐름을 몸으로 익힌다.
> 결과물: DB 없이 메모리에 저장되는 티켓 CRUD API 5개.

## 만든 것

```
app/
├── server.py                  # 앱 생성 + 라우터 연결 (입구)
├── api/v1/ticket_router.py    # /tickets 엔드포인트 5개
├── models/api/ticket_api.py   # 요청·응답 스키마 (Pydantic)
└── core/config.py             # .env → Settings 객체
.env.example                   # 환경변수 템플릿 (.env는 git 제외)
```

| 메서드 | 경로 | 하는 일 | 응답 코드 |
| --- | --- | --- | --- |
| GET | `/health` | 서버 살아있는지 + 현재 env | 200 |
| GET | `/tickets` | 티켓 목록 | 200 |
| GET | `/tickets/{id}` | 티켓 하나 | 200 / 404 |
| POST | `/tickets` | 티켓 생성 | 201 / 422 |
| PATCH | `/tickets/{id}` | 일부 수정 | 200 / 404 |
| DELETE | `/tickets/{id}` | 삭제 | 204 / 404 |

## 요청 한 번의 흐름

`POST /tickets` 에 `{"title": "login bug"}` 가 오면:

```
브라우저/프론트 fetch
    │
    ▼
uvicorn  ─ 포트 8000에서 요청을 받아 app 에 넘김
    │
    ▼
server.py (app)  ─ 경로를 보고 ticket_router 로 넘김
    │
    ▼
ticket_router.create_ticket(body: TicketCreate)
    │   ① body 를 TicketCreate 모양으로 검증 (틀리면 422)
    │   ② dict 에 저장
    │   ③ dict 반환
    ▼
response_model=TicketResponse  ─ 반환값을 응답 모양으로 걸러서 JSON 으로
    │
    ▼
201 {"id": 1, "title": "login bug", "description": null, "status": "open"}
```

## 핵심 개념 4개

### 1. `server.py` 는 조립하는 곳

```python
app = FastAPI(title="ticket-api")      # 서버 한 대
app.include_router(ticket_router)      # 라우터 붙이기
```

- Express 의 `const app = express()` + `app.use(router)` 와 같다.
- 실제 로직은 여기 없다. 라우터·미들웨어·예외 핸들러를 **붙이기만** 한다.
- 실행은 `uvicorn app.server:app` → `app` 폴더의 `server.py` 안의 `app` 변수.

### 2. `APIRouter` 는 엔드포인트 묶음

```python
router = APIRouter(prefix="/tickets", tags=["tickets"])

@router.get("/{ticket_id}")
def get_ticket(ticket_id: int) -> dict: ...
```

- `prefix` 덕분에 `""` → `/tickets`, `"/{ticket_id}"` → `/tickets/3`.
- 경로의 `{ticket_id}` 는 같은 이름의 함수 인자로 들어온다. `: int` 라서 `/tickets/abc` 는 자동 422.
- 에러는 `return` 이 아니라 `raise HTTPException(404, ...)`. FastAPI 가 받아서 JSON 응답으로 바꾼다.
- 도메인마다 라우터 파일 하나 (`ticket_router.py`, 나중에 `auth_router.py`, `audit_router.py`).

### 3. Pydantic = 데이터 모양 선언 + 자동 검증

```python
class TicketCreate(BaseModel):
    title: str = Field(min_length=1)     # 필수, 1글자 이상
    description: str | None = None       # 선택
```

| zod | Pydantic |
| --- | --- |
| `z.object({...})` | `class X(BaseModel):` |
| `z.string().min(1)` | `title: str = Field(min_length=1)` |
| `z.string().optional()` | `description: str \| None = None` |
| `schema.parse(data)` | `X.model_validate(data)` / 라우터 인자에 타입만 적으면 자동 |
| 객체로 변환 | `x.model_dump()` |

같은 "티켓"인데 모델이 3개인 이유:

| 모델 | 용도 | 특징 |
| --- | --- | --- |
| `TicketCreate` | 생성 요청 | `id`, `status` 없음 (서버가 정함) |
| `TicketUpdate` | 일부 수정 요청 | 전부 선택. `model_dump(exclude_unset=True)` 로 보낸 것만 꺼냄 |
| `TicketResponse` | 응답 | 전부 필수. `response_model=` 에 지정하면 없는 필드는 응답에서 빠짐 |

### 4. `Depends` = "이거 필요해" 라고 선언하면 FastAPI 가 넣어줌

```python
@app.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]):
    return {"status": "ok", "env": settings.app_env}
```

요청이 오면 FastAPI 가:
1. `health` 에 `settings` 인자가 필요한 걸 본다
2. `Depends(get_settings)` 이니 `get_settings()` 를 먼저 실행
3. 결과를 `settings` 에 넣고 `health()` 실행

- `Annotated[타입, Depends(함수)]` — 타입과 "구하는 방법"을 한 자리에 적는 문법. 이 모양 그대로 외운다.
- React 커스텀 훅 `const settings = useSettings()` 와 같은 느낌. 어디서 오는지 몰라도 그냥 쓴다.
- **왜 중요한가:** 회사 코드는 로그인 사용자, DB 연결, 서비스 객체를 전부 이 방식으로 받는다.
  ```python
  def approve(ticket_id: int,
              user: Annotated[User, Depends(get_current_user)],
              db: Annotated[Database, Depends(get_db)]): ...
  ```
  1주차에 본 `settings` 하나와 완전히 같은 모양이 반복된다.

## 설정 파일 (`core/config.py`)

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    app_env: str = "dev"      # .env 에 없으면 "dev"
    jwt_secret: str           # 없으면 서버 시작 실패

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- `.env` 의 `APP_ENV=dev` → `settings.app_env`. 대소문자 무시.
- 프론트 `import.meta.env.VITE_X` 와 다른 점: 필수값이 빠지면 조용히 `undefined` 가 아니라 **시작부터 막힌다**.
- `@lru_cache` 로 한 번만 만들어 재사용 (요청마다 `.env` 를 다시 읽지 않음).
- `.env` 는 비밀값이라 git 제외, `.env.example` 만 올린다.

## 용어 정리

| 용어 | 뜻 | 프론트 대응 |
| --- | --- | --- |
| 엔드포인트 | "주소 + 메서드 → 함수" 짝 하나 | `fetch` 가 호출하는 대상 |
| 라우터 | 엔드포인트 묶음 파일 | `express.Router()`, 페이지별 컴포넌트 파일 |
| 데코레이터 `@` | 함수 위에 붙여 등록·변형하는 문법 | `app.get("/x", handler)` 의 다른 모양 |
| 패키지 / 모듈 | 폴더 (`__init__.py` 있는) / `.py` 파일 | 폴더 / 파일 |
| 가상환경 `.venv` | 프로젝트별 패키지 설치 폴더 | `node_modules` |
| `uv.lock` | 정확한 설치 버전 고정 | `package-lock.json` |
| docstring `"""..."""` | 클래스·함수 설명 주석. `/docs` 에도 표시 | JSDoc |
| 422 | 요청 데이터 모양이 틀림 (Pydantic 검증 실패) | zod parse 실패 |

## 삽질 기록

- `uv` 명령을 못 찾음 → 설치 후 터미널(VS Code)을 재시작하지 않아 PATH 미반영.
- `ModuleNotFoundError: No module named 'app'` → `app/` 폴더를 만들기 전에 실행함. `uvicorn app.server:app` 은 "app 폴더 / server.py / app 변수".
- `/docs` 에 새 엔드포인트가 안 보임 → 같은 포트에 옛날 서버 프로세스가 남아 있었음. 서버는 시작할 때 코드를 읽으므로 `--reload` 를 붙이거나 재시작해야 한다.

## 아직 회사 구조와 다른 점 (다음 주차에 고침)

- 라우터가 저장소(`_tickets` dict)를 직접 만진다 → 3주차에 라우터 → 서비스 → 리포지토리로 분리
- 저장소가 메모리라 서버 끄면 사라짐 → 2주차에 MongoDB
- 인증 없음 → 4주차 JWT + RBAC
- 함수가 `def` → 2주차부터 `async def` (DB 호출이 비동기라서)

## 2주차 준비물

- Docker Desktop 설치 (MongoDB 를 컨테이너로 띄움)
- MongoDB Compass 설치 (데이터 눈으로 보기, 선택)
