from pydantic import BaseModel, Field

from app.models.db.users import Role


class SignupRequest(BaseModel):
    """POST /auth/signup 요청 본문."""

    email: str = Field(min_length=3, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    """POST /auth/login 요청 본문. 성공하면 토큰은 본문이 아니라 Set-Cookie 로 내려간다."""

    email: str
    password: str


class UserResponse(BaseModel):
    """사용자 정보 응답. UserDoc 에서 password_hash 를 뺀 것."""

    id: str
    email: str
    role: Role
    groups: list[str]
