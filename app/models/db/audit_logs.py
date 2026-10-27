from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.db.tickets import ObjectIdStr

# 기록할 행동의 종류. "도메인.동사" 형태로 적어 두면 나중에 필터링하기 쉽다.
AuditAction = Literal[
    "ticket.created",
    "ticket.updated",
    "ticket.approved",
    "ticket.rejected",
    "ticket.deleted",
]


class AuditLogDoc(BaseModel):
    """audit_logs 컬렉션의 문서 한 건. '누가 언제 무엇을 어떻게 바꿨나'."""

    model_config = ConfigDict(populate_by_name=True)

    id: ObjectIdStr = Field(alias="_id")
    ticket_id: str
    action: AuditAction
    actor: str = "system"  # 4주차에 로그인한 사용자 id 로 교체된다
    before: dict[str, Any] | None = None  # 바뀌기 전 값 (생성이면 None)
    after: dict[str, Any] | None = None  # 바뀐 후 값 (삭제면 None)
    created_at: datetime
