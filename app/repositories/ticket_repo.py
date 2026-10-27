from datetime import UTC, datetime
from typing import Annotated, Any

from bson import ObjectId
from fastapi import Depends
from pymongo import ASCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.core.db import get_db
from app.models.db.tickets import TicketDoc


class TicketRepository:
    """tickets 컬렉션에 대한 모든 Mongo 쿼리는 여기에만 둔다.

    라우터/서비스는 Mongo 문법을 몰라도 되게, 파이썬 메서드로 감싼다.
    권한은 모른다 — 서비스가 넘겨주는 scope 필터를 그대로 쿼리에 섞을 뿐이다.
    """

    def __init__(self, db: AsyncDatabase) -> None:
        self._col = db["tickets"]

    async def ensure_indexes(self) -> None:
        """서버 시작 시 1회. 이미 있으면 아무 일도 안 한다."""
        await self._col.create_index([("status", ASCENDING)])
        await self._col.create_index([("created_at", ASCENDING)])
        await self._col.create_index([("group_id", ASCENDING)])  # 그룹 스코핑 조회용
        await self._col.create_index([("owner_id", ASCENDING)])  # OWNER 조회용

    async def list(
        self, scope: dict[str, Any], *, skip: int = 0, limit: int = 20
    ) -> list[TicketDoc]:
        cursor = self._col.find(scope).sort("created_at", ASCENDING).skip(skip).limit(limit)
        return [TicketDoc.model_validate(doc) async for doc in cursor]

    async def get(self, ticket_id: ObjectId) -> TicketDoc | None:
        doc = await self._col.find_one({"_id": ticket_id})
        return TicketDoc.model_validate(doc) if doc else None

    async def create(self, data: dict[str, Any]) -> TicketDoc:
        now = datetime.now(UTC)
        doc = {**data, "status": "open", "created_at": now, "updated_at": now}
        result = await self._col.insert_one(doc)
        return TicketDoc.model_validate({**doc, "_id": result.inserted_id})

    async def update(self, ticket_id: ObjectId, changes: dict[str, Any]) -> TicketDoc | None:
        doc = await self._col.find_one_and_update(
            {"_id": ticket_id},
            {"$set": {**changes, "updated_at": datetime.now(UTC)}},
            return_document=True,  # 바뀐 후의 문서를 돌려받는다
        )
        return TicketDoc.model_validate(doc) if doc else None

    async def delete(self, ticket_id: ObjectId) -> bool:
        result = await self._col.delete_one({"_id": ticket_id})
        return result.deleted_count == 1


def get_ticket_repo(db: Annotated[AsyncDatabase, Depends(get_db)]) -> TicketRepository:
    """의존성 체인: get_db → get_ticket_repo → 서비스."""
    return TicketRepository(db)
