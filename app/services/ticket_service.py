from typing import Annotated, Any

from bson import ObjectId
from fastapi import Depends

from app.core.exceptions import InvalidTransitionError, NotFoundError
from app.models.db.tickets import TicketDoc, TicketStatus
from app.repositories.ticket_repo import TicketRepository, get_ticket_repo

# 상태 전이 규칙: {현재 상태: 갈 수 있는 상태들}
_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    "open": {"approved", "rejected"},
    "approved": set(),
    "rejected": set(),
}


class TicketService:
    """티켓에 관한 비즈니스 규칙. HTTP 도 Mongo 도 모른다.

    - 라우터: 요청을 받아 서비스에 넘기고 응답으로 변환
    - 서비스: "이게 되는 일인가" 판단 (없으면 NotFoundError, 안 되는 전이면 InvalidTransitionError)
    - 리포지토리: DB 읽고 쓰기
    """

    def __init__(self, repo: TicketRepository) -> None:
        self._repo = repo

    async def list(self, *, skip: int, limit: int) -> list[TicketDoc]:
        return await self._repo.list(skip=skip, limit=limit)

    async def get(self, ticket_id: str) -> TicketDoc:
        ticket = await self._repo.get(self._to_object_id(ticket_id))
        if ticket is None:
            raise NotFoundError(f"Ticket {ticket_id} not found")
        return ticket

    async def create(self, data: dict[str, Any]) -> TicketDoc:
        return await self._repo.create(data)

    async def update(self, ticket_id: str, changes: dict[str, Any]) -> TicketDoc:
        ticket = await self._repo.update(self._to_object_id(ticket_id), changes)
        if ticket is None:
            raise NotFoundError(f"Ticket {ticket_id} not found")
        return ticket

    async def delete(self, ticket_id: str) -> None:
        deleted = await self._repo.delete(self._to_object_id(ticket_id))
        if not deleted:
            raise NotFoundError(f"Ticket {ticket_id} not found")

    async def approve(self, ticket_id: str) -> TicketDoc:
        return await self._transition(ticket_id, "approved")

    async def reject(self, ticket_id: str) -> TicketDoc:
        return await self._transition(ticket_id, "rejected")

    async def _transition(self, ticket_id: str, to: TicketStatus) -> TicketDoc:
        ticket = await self.get(ticket_id)  # 없으면 여기서 NotFoundError
        if to not in _TRANSITIONS[ticket.status]:
            raise InvalidTransitionError(f"Cannot move ticket from '{ticket.status}' to '{to}'")
        updated = await self._repo.update(self._to_object_id(ticket_id), {"status": to})
        assert updated is not None  # 방금 get 으로 존재를 확인했으므로
        return updated

    @staticmethod
    def _to_object_id(ticket_id: str) -> ObjectId:
        # 형식이 틀린 id 는 "존재하지 않는 것" 과 같게 취급한다.
        if not ObjectId.is_valid(ticket_id):
            raise NotFoundError(f"Ticket {ticket_id} not found")
        return ObjectId(ticket_id)


def get_ticket_service(repo: Annotated[TicketRepository, Depends(get_ticket_repo)]) -> TicketService:
    """의존성 체인: get_db → get_ticket_repo → get_ticket_service → 라우터."""
    return TicketService(repo)
