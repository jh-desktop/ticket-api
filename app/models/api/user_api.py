from pydantic import BaseModel

from app.models.db.users import Role


class UserRoleUpdate(BaseModel):
    """PATCH /users/{id}/role 요청 본문. ADMIN 이 다른 사용자의 역할과 그룹을 정한다."""

    role: Role
    groups: list[str] = []
