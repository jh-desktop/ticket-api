from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.rbac import require_role
from app.models.api.snapshot_api import SnapshotResponse
from app.models.db.users import UserDoc
from app.services.snapshot_service import SnapshotService, get_snapshot_service

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

Service = Annotated[SnapshotService, Depends(get_snapshot_service)]
Admin = Annotated[UserDoc, Depends(require_role("ADMIN"))]


@router.get("", response_model=list[SnapshotResponse])
async def list_snapshots(
    _: Admin,
    svc: Service,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
):
    """저장된 통계 이력, 최신순. (학습 UI 의 차트가 이걸 그린다)"""
    return await svc.list(skip=skip, limit=limit)
