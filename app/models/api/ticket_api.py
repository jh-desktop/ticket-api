from datetime import datetime

from pydantic import BaseModel, Field


class TicketCreate(BaseModel):
    """POST /tickets 요청 본문. 프론트가 티켓을 만들 때 보내는 데이터."""

    title: str = Field(min_length=1)
    description: str | None = None


class TicketUpdate(BaseModel):
    """PATCH /tickets/{id} 요청 본문. 바꾸고 싶은 필드만 보내면 된다."""

    title: str | None = Field(default=None, min_length=1)
    description: str | None = None


class TicketResponse(BaseModel):
    """서버가 돌려주는 티켓 한 건의 모양. DB 모델(TicketDoc)에서 내보낼 것만 고른다."""

    id: str
    title: str
    description: str | None
    status: str
    created_at: datetime
