from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.models.api.ticket_api import TicketCreate, TicketResponse, TicketUpdate
from app.services.ticket_service import TicketService, get_ticket_service

router = APIRouter(prefix="/tickets", tags=["tickets"])

Service = Annotated[TicketService, Depends(get_ticket_service)]


@router.get("", response_model=list[TicketResponse])
async def list_tickets(
    svc: Service,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return await svc.list(skip=skip, limit=limit)


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str, svc: Service):
    return await svc.get(ticket_id)


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(body: TicketCreate, svc: Service):
    return await svc.create(body.model_dump())


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(ticket_id: str, body: TicketUpdate, svc: Service):
    return await svc.update(ticket_id, body.model_dump(exclude_unset=True))


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(ticket_id: str, svc: Service) -> None:
    await svc.delete(ticket_id)


@router.post("/{ticket_id}/approve", response_model=TicketResponse)
async def approve_ticket(ticket_id: str, svc: Service):
    return await svc.approve(ticket_id)


@router.post("/{ticket_id}/reject", response_model=TicketResponse)
async def reject_ticket(ticket_id: str, svc: Service):
    return await svc.reject(ticket_id)
