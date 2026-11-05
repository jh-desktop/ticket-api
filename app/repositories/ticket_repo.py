from typing import Annotated, Any

from bson import ObjectId
from fastapi import Depends
from pymongo import ASCENDING

from app.core.clock import utcnow
from app.core.db import MongoDB, get_db
from app.core.trace import traced
from app.models.db.tickets import TicketDoc


@traced("repository")
class TicketRepository:
    """tickets 컬렉션에 대한 모든 Mongo 쿼리는 여기에만 둔다.

    라우터/서비스는 Mongo 문법을 몰라도 되게, 파이썬 메서드로 감싼다.
    권한은 모른다 — 서비스가 넘겨주는 scope 필터를 그대로 쿼리에 섞을 뿐이다.
    """

    def __init__(self, db: MongoDB) -> None:
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
        now = utcnow()
        doc = {**data, "status": "open", "created_at": now, "updated_at": now}
        result = await self._col.insert_one(doc)
        return TicketDoc.model_validate({**doc, "_id": result.inserted_id})

    async def update(self, ticket_id: ObjectId, changes: dict[str, Any]) -> TicketDoc | None:
        doc = await self._col.find_one_and_update(
            {"_id": ticket_id},
            {"$set": {**changes, "updated_at": utcnow()}},
            return_document=True,  # 바뀐 후의 문서를 돌려받는다
        )
        return TicketDoc.model_validate(doc) if doc else None

    async def delete(self, ticket_id: ObjectId) -> bool:
        result = await self._col.delete_one({"_id": ticket_id})
        return result.deleted_count == 1

    async def count_by(self, field: str) -> dict[str, int]:
        """필드 값별 개수. 예: count_by("status") → {"open": 3, "approved": 2}

        aggregation pipeline: 문서를 단계(stage)별로 흘려보내며 가공하는 Mongo 의 집계 기능.
        $group 은 SQL 의 GROUP BY. "_id" 에 묶을 기준을, 나머지에 집계식($sum 등)을 적는다.
        """
        pipeline = [{"$group": {"_id": f"${field}", "count": {"$sum": 1}}}]
        cursor = await self._col.aggregate(pipeline)
        return {str(row["_id"]): int(row["count"]) async for row in cursor}

    async def count(self) -> int:
        return await self._col.count_documents({})


def get_ticket_repo(db: Annotated[MongoDB, Depends(get_db)]) -> TicketRepository:
    """의존성 체인: get_db → get_ticket_repo → 서비스."""
    return TicketRepository(db)
