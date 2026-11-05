"""리포지토리 단위 테스트 — HTTP 없이 Mongo 쿼리만 검증한다 (pytest-asyncio).

API 테스트(TestClient)와 달리 여기선 테스트가 자기 이벤트 루프에서 AsyncMongoClient 를 직접 만든다.
앱의 전역 클라이언트(core/db.py)는 TestClient 의 루프에 묶여 있어 여기서 쓰면 안 된다.
"""

from collections.abc import AsyncIterator

import pytest
from bson import ObjectId
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import get_settings
from app.repositories.ticket_repo import TicketRepository


@pytest.fixture
async def repo() -> AsyncIterator[TicketRepository]:
    settings = get_settings()
    client: AsyncMongoClient[dict[str, object]] = AsyncMongoClient(settings.mongo_uri, tz_aware=True)
    db: AsyncDatabase[dict[str, object]] = client[settings.mongo_db_name]
    await db["tickets"].delete_many({})
    yield TicketRepository(db)
    await client.close()


async def test_create_get_update_delete_roundtrip(repo: TicketRepository) -> None:
    created = await repo.create({"title": "repo", "description": None, "owner_id": "u1", "group_id": "g1"})
    assert created.status == "open"
    assert ObjectId.is_valid(created.id)
    assert created.created_at == created.updated_at

    fetched = await repo.get(ObjectId(created.id))
    assert fetched is not None and fetched.title == "repo"

    updated = await repo.update(ObjectId(created.id), {"title": "repo2"})
    assert updated is not None
    assert updated.title == "repo2"
    assert updated.updated_at >= created.updated_at  # 같은 밀리초면 같을 수 있다

    assert await repo.delete(ObjectId(created.id)) is True
    assert await repo.get(ObjectId(created.id)) is None
    assert await repo.delete(ObjectId(created.id)) is False


async def test_list_applies_scope_filter(repo: TicketRepository) -> None:
    for owner, group in (("u1", "g1"), ("u2", "g1"), ("u3", "g2")):
        await repo.create({"title": f"{owner}-{group}", "description": None, "owner_id": owner, "group_id": group})

    assert len(await repo.list({})) == 3
    assert {t.title for t in await repo.list({"group_id": {"$in": ["g1"]}})} == {"u1-g1", "u2-g1"}
    assert [t.title for t in await repo.list({"owner_id": "u3"})] == ["u3-g2"]
    assert len(await repo.list({}, skip=1, limit=1)) == 1
