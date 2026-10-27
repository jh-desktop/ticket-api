from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

# Mongo 의 ObjectId 를 str 로 받아들이는 타입.
# BeforeValidator(str): 검증 전에 str() 을 한 번 거친다 → ObjectId("...") 가 "..." 문자열이 된다.
ObjectIdStr = Annotated[str, BeforeValidator(str)]


class TicketDoc(BaseModel):
    """tickets 컬렉션의 문서(document) 한 건. DB 에 저장된 모양 그대로."""

    # Mongo 는 id 를 "_id" 라는 이름으로 저장한다. 파이썬 쪽에서는 id 로 부르고 싶으므로 alias 로 연결.
    model_config = ConfigDict(populate_by_name=True)

    id: ObjectIdStr = Field(alias="_id")
    title: str
    description: str | None = None
    status: str = "open"
    created_at: datetime
    updated_at: datetime
