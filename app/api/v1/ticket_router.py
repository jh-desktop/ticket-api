from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.api.ticket_api import TicketCreate, TicketResponse, TicketUpdate
from app.repositories.ticket_repo import TicketRepository, get_ticket_repo

router = APIRouter(prefix="/tickets", tags=["tickets"])

# 라우터 함수마다 반복되는 타입을 별칭으로 묶어 둔다.
TicketRepo = Annotated[TicketRepository, Depends(get_ticket_repo)]


def _to_object_id(ticket_id: str) -> ObjectId:
    """경로의 문자열 id → ObjectId. 형식이 틀리면 존재하지 않는 것과 똑같이 404."""
    if not ObjectId.is_valid(ticket_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ObjectId(ticket_id)


@router.get("", response_model=list[TicketResponse])
async def list_tickets(
    repo: TicketRepo,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return await repo.list(skip=skip, limit=limit)


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str, repo: TicketRepo):
    ticket = await repo.get(_to_object_id(ticket_id))
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(body: TicketCreate, repo: TicketRepo):
    return await repo.create(body.model_dump())


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(ticket_id: str, body: TicketUpdate, repo: TicketRepo):
    changes = body.model_dump(exclude_unset=True)
    ticket = await repo.update(_to_object_id(ticket_id), changes)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(ticket_id: str, repo: TicketRepo) -> None:
    deleted = await repo.delete(_to_object_id(ticket_id))
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
