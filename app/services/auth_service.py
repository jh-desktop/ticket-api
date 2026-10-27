from typing import Annotated

from fastapi import Depends

from app.core.auth import create_access_token
from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.models.db.users import UserDoc
from app.repositories.user_repo import UserRepository, get_user_repo


class AuthService:
    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self._users = users
        self._settings = settings

    async def signup(self, *, email: str, password: str) -> UserDoc:
        if await self._users.get_by_email(email) is not None:
            raise ConflictError("Email already registered")
        return await self._users.create(
            {"email": email, "password_hash": hash_password(password), "role": "OWNER", "groups": []}
        )

    async def login(self, *, email: str, password: str) -> tuple[UserDoc, str]:
        """성공하면 (사용자, access token) 을 돌려준다. 쿠키에 싣는 건 라우터의 일.

        이메일이 없을 때와 비밀번호가 틀릴 때 메시지를 똑같이 한다 —
        '이 이메일은 가입돼 있다' 는 정보를 공격자에게 주지 않기 위해.
        """
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")
        return user, create_access_token(user, self._settings)


def get_auth_service(
    users: Annotated[UserRepository, Depends(get_user_repo)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(users, settings)
