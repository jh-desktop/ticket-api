import json
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.audit_router import router as audit_router
from app.api.v1.auth_router import router as auth_router
from app.api.v1.learn_router import router as learn_router
from app.api.v1.scheduler_endpoint import router as scheduler_router
from app.api.v1.snapshot_router import router as snapshot_router
from app.api.v1.ticket_router import router as ticket_router
from app.api.v1.user_router import router as user_router
from app.core import trace
from app.core.auth import decode_access_token, extract_token
from app.core.config import Settings, get_settings
from app.core.db import MongoDB, close_db, connect_db, get_db
from app.core.exceptions import AppError, UnauthorizedError, error_response, register_exception_handlers
from app.repositories.audit_repo import AuditRepository
from app.repositories.snapshot_repo import SnapshotRepository
from app.repositories.ticket_repo import TicketRepository
from app.repositories.user_repo import UserRepository

# 인증 없이 통과시키는 경로. 그 외 모든 요청은 미들웨어에서 토큰을 먼저 확인한다.
_NO_AUTH_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/auth/signup",
        "/auth/login",
        "/auth/logout",
    }
)
# 접두사로 통과시키는 경로.
#   /scheduler/* : 외부 K8s CronJob 이 호출 (네트워크 레벨에서만 보호)
#   /learn/*     : 학습 UI 용 문서·용어집 (dev 전용, 비밀 없음)
_NO_AUTH_PREFIXES: tuple[str, ...] = ("/scheduler/", "/learn/")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    # yield 전: 서버 시작 직후 실행
    await connect_db()
    await TicketRepository(get_db()).ensure_indexes()
    await AuditRepository(get_db()).ensure_indexes()
    await UserRepository(get_db()).ensure_indexes()
    await SnapshotRepository(get_db()).ensure_indexes()
    yield
    # yield 후: 서버 종료 직전 실행
    await close_db()


app = FastAPI(title="ticket-api", lifespan=lifespan)

register_exception_handlers(app)

Next = Callable[[Request], Awaitable[Response]]

# 미들웨어 순서: 나중에 등록한 것이 바깥쪽. 요청은 바깥 → 안쪽으로 들어온다.
#   CORS(가장 바깥) → trace → auth → 라우터
# 그래서 아래에서 auth 를 먼저, trace 를 그다음, CORS 를 마지막에 등록한다.


@app.middleware("http")
async def auth_middleware(request: Request, call_next: Next) -> Response:
    """모든 요청이 지나는 관문.

    - _NO_AUTH_PATHS / _NO_AUTH_PREFIXES 면 그냥 통과
    - 아니면 토큰이 있고 서명·만료가 유효한지만 확인. 틀리면 라우터까지 가지 않고 401
    - "누구인가(DB 조회)" 와 "무엇을 할 수 있나(RBAC)" 는 여기서 하지 않는다 — Depends(get_current_user) 와 서비스의 일
    """
    path = request.url.path
    if path in _NO_AUTH_PATHS or path.startswith(_NO_AUTH_PREFIXES) or request.method == "OPTIONS":
        trace.mark("middleware:auth skipped (public path)")
        return await call_next(request)

    token = extract_token(request)
    if token is None:
        trace.mark("middleware:auth DENIED (no token)")
        return error_response(UnauthorizedError("Not authenticated"))
    try:
        decode_access_token(token, get_settings())
    except AppError as exc:  # 만료/위조 → UnauthorizedError
        trace.mark(f"middleware:auth DENIED ({exc.message})")
        # 미들웨어에서 raise 한 예외는 exception_handler 를 거치지 않으므로 직접 응답을 만든다
        return error_response(exc)
    trace.mark("middleware:auth token ok")
    return await call_next(request)


@app.middleware("http")
async def trace_middleware(request: Request, call_next: Next) -> Response:
    """학습용. 요청이 지난 레이어 목록을 X-Trace 헤더로, 처리 시간을 X-Duration-Ms 로 돌려준다 (dev 에서만)."""
    trace.start()
    started = time.perf_counter()
    response = await call_next(request)
    if get_settings().app_env == "dev":
        steps = trace.steps()
        route = request.scope.get("route")
        endpoint = getattr(route, "endpoint", None)
        if endpoint is not None:
            # 라우터 지점은 미들웨어 바로 다음에 끼워 넣는다 (실제 실행 순서와 같게)
            mod = str(getattr(endpoint, "__module__", "")).rsplit(".", 1)[-1]
            after_mw = next((i for i, s in enumerate(steps) if not s.startswith("middleware:")), len(steps))
            steps.insert(after_mw, f"router:{mod}.{getattr(endpoint, '__name__', '?')}")
        response.headers["X-Request-Id"] = uuid4().hex[:8]
        response.headers["X-Duration-Ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
        response.headers["X-Trace"] = json.dumps(steps)
    return response


# 다른 출처(Vite dev server 등)의 브라우저가 쿠키를 주고받을 수 있게.
#   allow_credentials=True 일 때는 allow_origins 에 "*" 를 쓸 수 없다 (브라우저 규칙).
#   expose_headers: 프론트 JS 가 읽을 수 있게 허용할 응답 헤더.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Trace", "X-Request-Id", "X-Duration-Ms"],
)

app.include_router(auth_router)
app.include_router(ticket_router)
app.include_router(audit_router)
app.include_router(user_router)
app.include_router(snapshot_router)
app.include_router(scheduler_router)
app.include_router(learn_router)


@app.get("/health")
async def health(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[MongoDB, Depends(get_db)],
) -> dict[str, str]:
    await db.command("ping")
    return {"status": "ok", "env": settings.app_env, "db": db.name}
