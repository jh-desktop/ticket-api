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


def get_user_repo(db: Annotated[AsyncDatabase, Depends(get_db)]) -> UserRepository:
    return UserRepository(db)
