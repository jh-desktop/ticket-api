from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from pymongo.asynchronous.database import AsyncDatabase

from app.api.v1.audit_router import router as audit_router
from app.api.v1.auth_router import router as auth_router
from app.api.v1.ticket_router import router as ticket_router
from app.api.v1.user_router import router as user_router
from app.core.auth import decode_access_token, extract_token
from app.core.config import Settings, get_settings
from app.core.db import close_db, connect_db, get_db
from app.core.exceptions import AppError, UnauthorizedError, error_response, register_exception_handlers
from app.repositories.audit_repo import AuditRepository
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
# 접두사로 통과시키는 경로. 6주차: 외부 K8s CronJob 이 호출하는 /scheduler/* (네트워크 레벨에서만 보호)
_NO_AUTH_PREFIXES: tuple[str, ...] = ("/scheduler/",)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # yield 전: 서버 시작 직후 실행
    await connect_db()
    await TicketRepository(get_db()).ensure_indexes()
    await AuditRepository(get_db()).ensure_indexes()
    await UserRepository(get_db()).ensure_indexes()
    yield
    # yield 후: 서버 종료 직전 실행
    await close_db()


app = FastAPI(title="ticket-api", lifespan=lifespan)

register_exception_handlers(app)


@app.middleware("http")
async def auth_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """모든 요청이 지나는 관문.

    - _NO_AUTH_PATHS / _NO_AUTH_PREFIXES 면 그냥 통과
    - 아니면 토큰이 있고 서명·만료가 유효한지만 확인. 틀리면 라우터까지 가지 않고 401
    - "누구인가(DB 조회)" 와 "무엇을 할 수 있나(RBAC)" 는 여기서 하지 않는다 — Depends(get_current_user) 와 서비스의 일
    """
    path = request.url.path
    if path in _NO_AUTH_PATHS or path.startswith(_NO_AUTH_PREFIXES) or request.method == "OPTIONS":
        return await call_next(request)

    token = extract_token(request)
    if token is None:
        return error_response(UnauthorizedError("Not authenticated"))
    try:
        decode_access_token(token, get_settings())
    except AppError as exc:  # 만료/위조 → UnauthorizedError
        # 미들웨어에서 raise 한 예외는 exception_handler 를 거치지 않으므로 직접 응답을 만든다
        return error_response(exc)
    return await call_next(request)


app.include_router(auth_router)
app.include_router(ticket_router)
app.include_router(audit_router)
app.include_router(user_router)


@app.get("/health")
async def health(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncDatabase, Depends(get_db)],
) -> dict[str, str]:
    await db.command("ping")
    return {"status": "ok", "env": settings.app_env, "db": db.name}
