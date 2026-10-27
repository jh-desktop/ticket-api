from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.rbac import require_role
from app.models.api.auth_api import UserResponse
from app.models.api.user_api import UserRoleUpdate
from app.models.db.users import UserDoc
from app.services.user_service import UserService, get_user_service

router = APIRouter(prefix="/users", tags=["users"])

Service = Annotated[UserService, Depends(get_user_service)]
Admin = Annotated[UserDoc, Depends(require_role("ADMIN"))]


@router.get("", response_model=list[UserResponse])
async def list_users(
    _: Admin,
    svc: Service,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    return await svc.list(skip=skip, limit=limit)


@router.patch("/{user_id}/role", response_model=UserResponse)
async def set_user_role(user_id: str, body: UserRoleUpdate, _: Admin, svc: Service):
    """역할과 그룹 부여. 예: {"role": "GROUP_WRITER", "groups": ["backend", "mobile"]}"""
    return await svc.set_role(user_id, role=body.role, groups=body.groups)
