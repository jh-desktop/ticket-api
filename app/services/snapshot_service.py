from typing import Annotated

from fastapi import Depends

from app.models.db.snapshots import SnapshotDoc
from app.repositories.snapshot_repo import SnapshotRepository, get_snapshot_repo
from app.repositories.ticket_repo import TicketRepository, get_ticket_repo


class SnapshotService:
    """티켓 통계를 한 장 찍어 저장한다. 스케줄러(CronJob)가 주기적으로 부른다."""

    def __init__(self, snapshots: SnapshotRepository, tickets: TicketRepository) -> None:
        self._snapshots = snapshots
        self._tickets = tickets

    async def take(self) -> SnapshotDoc:
        total = await self._tickets.count()
        by_status = await self._tickets.count_by("status")
        by_group = await self._tickets.count_by("group_id")
        # 없는 상태는 0 으로 채워 둔다 — 차트를 그릴 때 키가 들쭉날쭉하지 않게
        by_status = {s: by_status.get(s, 0) for s in ("open", "approved", "rejected")}
        return await self._snapshots.insert({"total": total, "by_status": by_status, "by_group": by_group})

    async def list(self, *, skip: int, limit: int) -> list[SnapshotDoc]:
        return await self._snapshots.list(skip=skip, limit=limit)


def get_snapshot_service(
    snapshots: Annotated[SnapshotRepository, Depends(get_snapshot_repo)],
    tickets: Annotated[TicketRepository, Depends(get_ticket_repo)],
) -> SnapshotService:
    return SnapshotService(snapshots, tickets)
