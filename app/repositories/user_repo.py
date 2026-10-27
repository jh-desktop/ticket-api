# 클래스 안에서 `list` 라는 메서드를 정의하면 그 아래 줄부터 `list[str]` 의 list 가 메서드를 가리키게 된다.
# 아래 import 는 타입 힌트를 문자열로 미뤄 두어 그 충돌을 피한다.
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from bson import ObjectId
from fastapi import Depends
from pymongo import ASCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.core.db import get_db
from app.models.db.users import UserDoc


class UserRepository:
    def __init__(self, db: AsyncDatabase) -> None:
        self._col = db["users"]

    async def ensure_indexes(self) -> None:
        # unique=True: 같은 이메일로 두 번 insert 하면 Mongo 가 거부한다 (DuplicateKeyError)
        await self._col.create_index([("email", ASCENDING)], unique=True)

    async def count(self) -> int:
        return await self._col.count_documents({})

    async def list(self, *, skip: int = 0, limit: int = 50) -> list[UserDoc]:
        cursor = self._col.find().sort("created_at", ASCENDING).skip(skip).limit(limit)
        return [UserDoc.model_validate(doc) async for doc in cursor]

    async def get_by_email(self, email: str) -> UserDoc | None:
        doc = await self._col.find_one({"email": email})
        return UserDoc.model_validate(doc) if doc else None

    async def get(self, user_id: ObjectId) -> UserDoc | None:
        doc = await self._col.find_one({"_id": user_id})
        return UserDoc.model_validate(doc) if doc else None

    async def create(self, data: dict[str, Any]) -> UserDoc:
        doc = {**data, "created_at": datetime.now(UTC)}
        result = await self._col.insert_one(doc)
        return UserDoc.model_validate({**doc, "_id": result.inserted_id})

    async def update_role(self, user_id: ObjectId, *, role: str, groups: list[str]) -> UserDoc | None:
        doc = await self._col.find_one_and_update(
            {"_id": user_id}, {"$set": {"role": role, "groups": groups}}, return_document=True
        )
        return UserDoc.model_validate(doc) if doc else None


def get_user_repo(db: Annotated[AsyncDatabase, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)
