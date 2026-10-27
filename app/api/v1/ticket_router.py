from fastapi import APIRouter, HTTPException, status

from app.models.api.ticket_api import TicketCreate, TicketResponse, TicketUpdate

router = APIRouter(prefix="/tickets", tags=["tickets"])

# 1주차 임시 저장소. 2주차에 MongoDB로 교체한다.
# key: 티켓 id, value: 티켓 데이터(dict)
_tickets: dict[int, dict] = {}
_next_id = 1


@router.get("", response_model=list[TicketResponse])
def list_tickets() -> list[dict]:
    return list(_tickets.values())


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: int) -> dict:
    ticket = _tickets.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    return ticket


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
def create_ticket(body: TicketCreate) -> dict:
    global _next_id
    ticket = {
        "id": _next_id,
        "title": body.title,
        "description": body.description,
        "status": "open",
    }
    _tickets[_next_id] = ticket
    _next_id += 1
    return ticket


@router.patch("/{ticket_id}", response_model=TicketResponse)
def update_ticket(ticket_id: int, body: TicketUpdate) -> dict:
    ticket = _tickets.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    # exclude_unset=True: 프론트가 실제로 보낸 필드만 꺼낸다 (안 보낸 필드는 건드리지 않음)
    changes = body.model_dump(exclude_unset=True)
    ticket.update(changes)
    return ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(ticket_id: int) -> None:
    if ticket_id not in _tickets:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    del _tickets[ticket_id]
