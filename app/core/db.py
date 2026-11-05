from typing import Any

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings

# pymongo 의 클라이언트/DB/컬렉션은 "문서 타입" 을 제네릭으로 받는다 (TS 의 Collection<Doc> 같은 것).
# 우리는 문서를 dict 로 다루므로 그 타입을 한 번 정해 두고 모든 곳에서 재사용한다.
Document = dict[str, Any]
MongoDB = AsyncDatabase[Document]


class _Mongo:
    """앱 전체에서 하나만 쓰는 Mongo 연결을 담아 두는 상자."""

    client: AsyncMongoClient[Document] | None = None
    db: MongoDB | None = None


_mongo = _Mongo()


async def connect_db() -> None:
    """서버 시작 시 1회 호출. 클라이언트를 만들고 실제로 연결되는지 ping 으로 확인한다."""
    settings = get_settings()
    # tz_aware=True: Mongo 는 datetime 을 시간대 없는 UTC 로 저장한다. 읽을 때 UTC 시간대를 붙여 돌려주게 해서
    # 우리가 만든 datetime.now(UTC) 와 비교·연산이 가능하게 한다 (naive vs aware 비교는 TypeError).
    _mongo.client = AsyncMongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000, tz_aware=True)
    _mongo.db = _mongo.client[settings.mongo_db_name]
    await _mongo.client.admin.command("ping")


async def close_db() -> None:
    """서버 종료 시 1회 호출. 연결을 정리한다."""
    if _mongo.client is not None:
        await _mongo.client.close()
        _mongo.client = None
        _mongo.db = None


def get_db() -> MongoDB:
    """라우터/리포지토리에서 Depends(get_db) 로 받아 쓰는 의존성."""
    if _mongo.db is None:
        raise RuntimeError("DB is not connected. Is lifespan configured?")
    return _mongo.db
