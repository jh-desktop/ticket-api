from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings


class _Mongo:
    """앱 전체에서 하나만 쓰는 Mongo 연결을 담아 두는 상자."""

    client: AsyncMongoClient | None = None
    db: AsyncDatabase | None = None


_mongo = _Mongo()


async def connect_db() -> None:
    """서버 시작 시 1회 호출. 클라이언트를 만들고 실제로 연결되는지 ping 으로 확인한다."""
    settings = get_settings()
    _mongo.client = AsyncMongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
    _mongo.db = _mongo.client[settings.mongo_db_name]
    await _mongo.client.admin.command("ping")


async def close_db() -> None:
    """서버 종료 시 1회 호출. 연결을 정리한다."""
    if _mongo.client is not None:
        await _mongo.client.close()
        _mongo.client = None
        _mongo.db = None


def get_db() -> AsyncDatabase:
    """라우터/리포지토리에서 Depends(get_db) 로 받아 쓰는 의존성."""
    if _mongo.db is None:
        raise RuntimeError("DB is not connected. Is lifespan configured?")
    return _mongo.db
