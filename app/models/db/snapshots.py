from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.db.tickets import ObjectIdStr


class SnapshotDoc(BaseModel):
    """snapshots 컬렉션의 문서 한 건 — 특정 시각의 티켓 통계.

    외부 스케줄러(K8s CronJob)가 주기적으로 POST /scheduler/snapshots 를 호출해 쌓는다.
    '지금' 은 tickets 를 세면 되지만 '어제 이 시간엔 몇 개였나' 는 이 기록이 있어야 안다.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: ObjectIdStr = Field(alias="_id")
    taken_at: datetime
    total: int
    by_status: dict[str, int]  # {"open": 3, "approved": 2, "rejected": 1}
    by_group: dict[str, int]  # {"backend": 4, "mobile": 2}
