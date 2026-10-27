from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends
from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.core.db import get_db
from app.models.db.audit_logs import AuditLogDoc


class AuditRepository:
    """audit_logs 컬렉션. 추가(insert)와 조회(find)만 있고 수정·삭제는 없다 — 감사 로그는 고치지 않는다."""

    def __init__(self, db: AsyncDatabase) -> None:
        self._col = db["audit_logs"]

    async def ensure_indexes(self) -> None:
        # "이 티켓의 이력을 최신순으로" 가 가장 흔한 조회이므로 복합 인덱스
        await self._col.create_index([("ticket_id", ASCENDING), ("created_at", DESCENDING)])

    async def insert(self, data: dict[str, Any]) -> AuditLogDoc:
        doc = {**data, "created_at": datetime.now(UTC)}
        result = await self._col.insert_one(doc)
        return AuditLogDoc.model_validate({**doc, "_id": result.inserted_id})

    async def list(
        self, *, ticket_id: str | None = None, skip: int = 0, limit: int = 50
    ) -> list[AuditLogDoc]:
        query: dict[str, Any] = {"ticket_id": ticket_id} if ticket_id else {}
        # 같은 밀리초에 기록된 로그는 created_at 이 같으므로 _id(생성 순 증가)로 2차 정렬
        cursor = (
            self._col.find(query)
            .sort([("created_at", DESCENDING), ("_id", DESCENDING)])
            .skip(skip)
            .limit(limit)
        )
        return [AuditLogDoc.model_validate(doc) async for doc in cursor]


def get_audit_repo(db: Annotated[AsyncDatabase, Depends(get_db)]) -> AuditRepository:
    return AuditRepository(db)
