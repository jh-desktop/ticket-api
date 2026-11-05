from typing import Annotated, Any

from fastapi import Depends
from pymongo import DESCENDING

from app.core.clock import utcnow
from app.core.db import MongoDB, get_db
from app.core.trace import traced
from app.models.db.snapshots import SnapshotDoc


@traced("repository")
class SnapshotRepository:
    """snapshots 컬렉션. 감사 로그처럼 추가·조회만 있다 — 과거 통계는 고치지 않는다."""

    def __init__(self, db: MongoDB) -> None:
        self._col = db["snapshots"]

    async def ensure_indexes(self) -> None:
        await self._col.create_index([("taken_at", DESCENDING)])

    async def insert(self, data: dict[str, Any]) -> SnapshotDoc:
        doc = {**data, "taken_at": utcnow()}
        result = await self._col.insert_one(doc)
        return SnapshotDoc.model_validate({**doc, "_id": result.inserted_id})

    async def list(self, *, skip: int = 0, limit: int = 50) -> list[SnapshotDoc]:
        cursor = self._col.find().sort([("taken_at", DESCENDING), ("_id", DESCENDING)]).skip(skip).limit(limit)
        return [SnapshotDoc.model_validate(doc) async for doc in cursor]


def get_snapshot_repo(db: Annotated[MongoDB, Depends(get_db)]) -> SnapshotRepository:
    return SnapshotRepository(db)
