from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from pymongo.asynchronous.database import AsyncDatabase

from app.api.v1.ticket_router import router as ticket_router
from app.core.config import Settings, get_settings
from app.core.db import close_db, connect_db, get_db


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # yield 전: 서버 시작 직후 실행
    await connect_db()
    yield
    # yield 후: 서버 종료 직전 실행
    await close_db()


app = FastAPI(title="ticket-api", lifespan=lifespan)

app.include_router(ticket_router)


@app.get("/health")
async def health(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncDatabase, Depends(get_db)],
) -> dict[str, str]:
    await db.command("ping")
    return {"status": "ok", "env": settings.app_env, "db": db.name}
