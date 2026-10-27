from typing import Annotated, Any

from fastapi import Depends

from app.models.db.audit_logs import AuditAction, AuditLogDoc
from app.repositories.audit_repo import AuditRepository, get_audit_repo


class AuditService:
    """감사 로그를 남기고 조회한다. 다른 서비스(티켓 등)가 '기록해 줘' 하고 부른다."""

    def __init__(self, repo: AuditRepository) -> None:
        self._repo = repo

    async def record(
        self,
        *,
        ticket_id: str,
        action: AuditAction,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        actor: str = "system",
    ) -> AuditLogDoc:
        return await self._repo.insert(
            {
                "ticket_id": ticket_id,
                "action": action,
                "actor": actor,
                "before": before,
                "after": after,
            }
        )

    async def list(
        self, *, ticket_id: str | None = None, skip: int = 0, limit: int = 50
    ) -> list[AuditLogDoc]:
        return await self._repo.list(ticket_id=ticket_id, skip=skip, limit=limit)


def get_audit_service(repo: Annotated[AuditRepository, Depends(get_audit_repo)]) -> AuditService:
    return AuditService(repo)
