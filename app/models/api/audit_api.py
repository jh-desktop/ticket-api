from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.db.audit_logs import AuditAction


class AuditLogResponse(BaseModel):
    """GET /audit-logs 응답 한 건."""

    id: str
    ticket_id: str
    action: AuditAction
    actor: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    created_at: datetime
