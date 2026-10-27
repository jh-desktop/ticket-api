from datetime import datetime

from pydantic import BaseModel, Field

from app.models.db.tickets import TicketStatus


class TicketCreate(BaseModel):
    """POST /tickets 요청 본문. owner_id 는 로그인 사용자에서 자동으로 채우므로 받지 않는다."""

    title: str = Field(min_length=1)
    description: str | None = None
    group_id: str = Field(min_length=1)


class TicketUpdate(BaseModel):
    """PATCH /tickets/{id} 요청 본문. 바꾸고 싶은 필드만 보내면 된다. (status/owner/group 은 여기로 못 바꿈)"""

    title: str | None = Field(default=None, min_length=1)
    description: str | None = None


class TicketResponse(BaseModel):
    """서버가 돌려주는 티켓 한 건의 모양. DB 모델(TicketDoc)에서 내보낼 것만 고른다."""

    id: str
    title: str
    description: str | None
    status: TicketStatus
    owner_id: str
    group_id: str
    created_at: datetime
