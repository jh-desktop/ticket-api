from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.core.auth import CurrentUser, clear_auth_cookie, set_auth_cookie
from app.core.config import Settings, get_settings
from app.models.api.auth_api import LoginRequest, SignupRequest, UserResponse
from app.services.auth_service import AuthService, get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

Service = Annotated[AuthService, Depends(get_auth_service)]
Config = Annotated[Settings, Depends(get_settings)]


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, svc: Service):
    return await svc.signup(email=body.email, password=body.password)


@router.post("/login", response_model=UserResponse)
async def login(body: LoginRequest, response: Response, svc: Service, settings: Config):
    """성공 시 access_token 을 HttpOnly 쿠키로 심고, 본문에는 사용자 정보를 돌려준다.

    `response: Response` 인자를 선언하면 FastAPI 가 '이번 응답 객체' 를 넣어 준다.
    거기에 쿠키를 붙이면 최종 응답에 Set-Cookie 헤더가 실린다.
    """
    user, token = await svc.login(email=body.email, password=body.password)
    set_auth_cookie(response, token, settings)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    clear_auth_cookie(response)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser):
    """쿠키의 토큰이 가리키는 사용자. 로그인 상태 확인용 (프론트 초기 로딩 때 호출)."""
    return user
