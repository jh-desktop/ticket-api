from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.models.api.audit_api import AuditLogResponse
from app.services.audit_service import AuditService, get_audit_service

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])

Service = Annotated[AuditService, Depends(get_audit_service)]


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    svc: Service,
    ticket_id: Annotated[str | None, Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """최신순. ?ticket_id=... 를 주면 그 티켓의 이력만."""
    return await svc.list(ticket_id=ticket_id, skip=skip, limit=limit)
