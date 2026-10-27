from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from pymongo.asynchronous.database import AsyncDatabase

from app.api.v1.audit_router import router as audit_router
from app.api.v1.auth_router import router as auth_router
from app.api.v1.ticket_router import router as ticket_router
from app.api.v1.user_router import router as user_router
from app.core.config import Settings, get_settings
from app.core.db import close_db, connect_db, get_db
from app.core.exceptions import register_exception_handlers
from app.repositories.audit_repo import AuditRepository
from app.repositories.ticket_repo import TicketRepository
from app.repositories.user_repo import UserRepository


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
