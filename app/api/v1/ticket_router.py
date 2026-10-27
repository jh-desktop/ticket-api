from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.auth import CurrentUser
from app.core.rbac import require_role
from app.models.api.ticket_api import TicketCreate, TicketResponse, TicketUpdate
from app.models.db.users import UserDoc
from app.services.ticket_service import TicketService, get_ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])

Service = Annotated[TicketService, Depends(get_ticket_service)]
# 승인/반려는 역할 자체가 ADMIN 또는 GROUP_WRITER 여야 입구를 통과한다. "어느 그룹인가" 는 서비스가 본다.
Approver = Annotated[UserDoc, Depends(require_role("ADMIN", "GROUP_WRITER"))]


@router.get("", response_model=list[TicketResponse])
async def list_tickets(
    user: CurrentUser,
    svc: Service,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """내가 볼 수 있는 티켓만. (ADMIN 전부 / 그룹 역할은 내 그룹 / OWNER 는 내 것)"""
    return await svc.list(user, skip=skip, limit=limit)


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str, user: CurrentUser, svc: Service):
    return await svc.get(user, ticket_id)


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(body: TicketCreate, user: CurrentUser, svc: Service):
    return await svc.create(user, body.model_dump())


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(ticket_id: str, body: TicketUpdate, user: CurrentUser, svc: Service):
    return await svc.update(user, ticket_id, body.model_dump(exclude_unset=True))


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(ticket_id: str, user: CurrentUser, svc: Service) -> None:
    await svc.delete(user, ticket_id)


@router.post("/{ticket_id}/approve", response_model=TicketResponse)
async def approve_ticket(ticket_id: str, user: Approver, svc: Service):
    return await svc.approve(user, ticket_id)


@router.post("/{ticket_id}/reject", response_model=TicketResponse)
async def reject_ticket(ticket_id: str, user: Approver, svc: Service):
    return await svc.reject(user, ticket_id)
