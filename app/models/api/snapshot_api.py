from datetime import datetime

from pydantic import BaseModel


class SnapshotResponse(BaseModel):
    id: str
    taken_at: datetime
    total: int
    by_status: dict[str, int]
    by_group: dict[str, int]
