from typing import Annotated, Any

from bson import ObjectId
from fastapi import Depends

from app.core import rbac
from app.core.exceptions import InvalidTransitionError, NotFoundError
from app.models.db.audit_logs import AuditAction
from app.models.db.tickets import TicketDoc, TicketStatus
from app.models.db.users import UserDoc
from app.repositories.ticket_repo import TicketRepository, get_ticket_repo
from app.services.audit_service import AuditService, get_audit_service

# 상태 전이 규칙: {현재 상태: 갈 수 있는 상태들}
_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    "open": {"approved", "rejected"},
    "approved": set(),
    "rejected": set(),
}

# 감사 로그에 남길 필드. id/시각 같은 메타는 제외.
_AUDITED_FIELDS = {"title", "description", "status", "group_id"}


def _snapshot(ticket: TicketDoc) -> dict[str, Any]:
    return ticket.model_dump(include=_AUDITED_FIELDS)


class TicketService:
    """티켓에 관한 비즈니스 규칙. HTTP 도 Mongo 도 모른다.

    모든 메서드가 actor(지금 요청한 사용자)를 받는다. 규칙은 세 단계로 적용된다.
    1. 조회 범위: rbac.scope_filter(actor) 를 쿼리에 섞는다
    2. 볼 수 없는 티켓은 '없는 것' 으로 취급한다 (404) — 존재 여부를 흘리지 않기 위해
    3. 볼 수는 있지만 할 수 없는 행위는 403
    """

    def __init__(self, repo: TicketRepository, audit: AuditService) -> None:
        self._repo = repo
        self._audit = audit

    async def list(self, actor: UserDoc, *, skip: int, limit: int) -> list[TicketDoc]:
        return await self._repo.list(rbac.scope_filter(actor), skip=skip, limit=limit)

    async def get(self, actor: UserDoc, ticket_id: str) -> TicketDoc:
        ticket = await self._repo.get(self._to_object_id(ticket_id))
        if ticket is None or not rbac.can_view(actor, ticket):
            raise NotFoundError(f"Ticket {ticket_id} not found")
        return ticket

    async def create(self, actor: UserDoc, data: dict[str, Any]) -> TicketDoc:
        rbac.ensure(rbac.can_create(actor, data["group_id"]), f"Cannot create tickets in group '{data['group_id']}'")
        ticket = await self._repo.create({**data, "owner_id": actor.id})
        await self._record(actor, ticket.id, "ticket.created", after=_snapshot(ticket))
        return ticket

    async def update(self, actor: UserDoc, ticket_id: str, changes: dict[str, Any]) -> TicketDoc:
        before = await self.get(actor, ticket_id)
        rbac.ensure(rbac.can_edit(actor, before), "Only the owner or an admin can edit this ticket")
        updated = await self._repo.update(self._to_object_id(ticket_id), changes)
        assert updated is not None
        await self._record(
            actor,
            ticket_id,
            "ticket.updated",
            before={k: getattr(before, k) for k in changes},  # 바뀐 필드만
            after=changes,
        )
        return updated

    async def delete(self, actor: UserDoc, ticket_id: str) -> None:
        before = await self.get(actor, ticket_id)
        rbac.ensure(rbac.can_edit(actor, before), "Only the owner or an admin can delete this ticket")
        await self._repo.delete(self._to_object_id(ticket_id))
        await self._record(actor, ticket_id, "ticket.deleted", before=_snapshot(before))

    async def approve(self, actor: UserDoc, ticket_id: str) -> TicketDoc:
        return await self._transition(actor, ticket_id, "approved", action="ticket.approved")

    async def reject(self, actor: UserDoc, ticket_id: str) -> TicketDoc:
        return await self._transition(actor, ticket_id, "rejected", action="ticket.rejected")

    async def _transition(
        self, actor: UserDoc, ticket_id: str, to: TicketStatus, *, action: AuditAction
    ) -> TicketDoc:
        ticket = await self.get(actor, ticket_id)  # 없거나 못 보면 404
        rbac.ensure(rbac.can_transition(actor, ticket), "Only an admin or a writer of this group can approve/reject")
        if to not in _TRANSITIONS[ticket.status]:
            raise InvalidTransitionError(f"Cannot move ticket from '{ticket.status}' to '{to}'")
        updated = await self._repo.update(self._to_object_id(ticket_id), {"status": to})
        assert updated is not None
        await self._record(actor, ticket_id, action, before={"status": ticket.status}, after={"status": to})
        return updated

    async def _record(
        self,
        actor: UserDoc,
        ticket_id: str,
        action: AuditAction,
        *,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
    ) -> None:
        await self._audit.record(ticket_id=ticket_id, action=action, actor=actor.id, before=before, after=after)

    @staticmethod
    def _to_object_id(ticket_id: str) -> ObjectId:
        # 형식이 틀린 id 는 "존재하지 않는 것" 과 같게 취급한다.
        if not ObjectId.is_valid(ticket_id):
            raise NotFoundError(f"Ticket {ticket_id} not found")
        return ObjectId(ticket_id)


def get_ticket_service(
    repo: Annotated[TicketRepository, Depends(get_ticket_repo)],
    audit: Annotated[AuditService, Depends(get_audit_service)],
) -> TicketService:
    """의존성 체인: get_db → (get_ticket_repo, get_audit_repo → get_audit_service) → get_ticket_service → 라우터."""
    return TicketService(repo, audit)
