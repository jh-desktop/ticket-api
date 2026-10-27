from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.db.tickets import ObjectIdStr

# 회사와 같은 4종. 의미는 4주차 RBAC 에서.
Role = Literal["ADMIN", "GROUP_WRITER", "GROUP_READER", "OWNER"]


class UserDoc(BaseModel):
    """users 컬렉션의 문서 한 건. password_hash 는 절대 API 응답으로 나가면 안 된다."""

    model_config = ConfigDict(populate_by_name=True)

    id: ObjectIdStr = Field(alias="_id")
    email: str
    password_hash: str
    role: Role = "OWNER"
    groups: list[str] = []
    created_at: datetime
