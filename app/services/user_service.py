from __future__ import annotations  # `list` 메서드와 `list[str]` 타입 힌트 충돌 회피 (user_repo.py 참고)

from typing import Annotated

from bson import ObjectId
from fastapi import Depends

from app.core.exceptions import NotFoundError
from app.models.db.users import Role, UserDoc
from app.repositories.user_repo import UserRepository, get_user_repo


class UserService:
    """사용자 관리 (ADMIN 용). 인증(가입/로그인)은 AuthService 가 따로 맡는다."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def list(self, *, skip: int, limit: int) -> list[UserDoc]:
        return await self._users.list(skip=skip, limit=limit)

    async def set_role(self, user_id: str, *, role: Role, groups: list[str]) -> UserDoc:
        if not ObjectId.is_valid(user_id):
            raise NotFoundError(f"User {user_id} not found")
        user = await self._users.update_role(ObjectId(user_id), role=role, groups=groups)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user


def get_user_service(users: Annotated[UserRepository, Depends(get_user_repo)]) -> UserService:
    return UserService(users)
