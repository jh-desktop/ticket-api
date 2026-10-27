from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
from bson import ObjectId
from fastapi import Depends, Request, Response

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorizedError
from app.models.db.users import UserDoc
from app.repositories.user_repo import UserRepository, get_user_repo

_ALGORITHM = "HS256"
COOKIE_NAME = "access_token"


def create_access_token(user: UserDoc, settings: Settings) -> str:
    """사용자 정보를 담은 JWT 발급. 서명은 JWT_SECRET 으로, 유효기간은 JWT_EXPIRE_MINUTES."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user.id,  # subject: 누구의 토큰인가
        "role": user.role,
        "groups": user.groups,
        "iat": now,  # issued at
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),  # expiration
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """서명과 만료를 검증하고 payload 를 돌려준다. 실패하면 UnauthorizedError."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token expired") from None
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token") from None


def set_auth_cookie(response: Response, token: str, settings: Settings) -> None:
    """로그인 성공 시 토큰을 HttpOnly 쿠키로 심는다. 이후 브라우저가 모든 요청에 자동으로 붙인다."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=settings.jwt_expire_minutes * 60,
        httponly=True,  # JS(document.cookie)에서 못 읽음 → XSS 로 토큰 탈취 방지
        secure=settings.cookie_secure,  # True 면 HTTPS 에서만 전송. 로컬(http)은 False
        samesite="lax",  # 다른 사이트에서 시작된 요청엔 안 붙음 → CSRF 완화
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    """로그아웃: 쿠키 삭제."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


def _extract_token(request: Request) -> str | None:
    """쿠키 우선, 없으면 Authorization: Bearer 헤더 (CronJob·스크립트 등 브라우저가 아닌 호출용)."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.removeprefix("Bearer ").strip()
    return None


async def get_current_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    users: Annotated[UserRepository, Depends(get_user_repo)],
) -> UserDoc:
    """라우터에서 Depends(get_current_user) 로 받으면 '지금 요청한 사용자' 가 들어온다.

    토큰이 없거나 틀리면 UnauthorizedError(401) 가 나서 라우터 본문은 실행되지 않는다.
    """
    token = _extract_token(request)
    if token is None:
        raise UnauthorizedError("Not authenticated")
    payload = decode_access_token(token, settings)
    user_id = payload.get("sub")
    if not user_id or not ObjectId.is_valid(user_id):
        raise UnauthorizedError("Invalid token")
    user = await users.get(ObjectId(user_id))
    if user is None:
        raise UnauthorizedError("User no longer exists")
    return user


CurrentUser = Annotated[UserDoc, Depends(get_current_user)]
