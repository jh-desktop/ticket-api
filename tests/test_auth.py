import time
from typing import Any

import jwt
import pytest
import httpx

from app.core.config import get_settings
from tests.conftest import PASSWORD, Actor

# ── signup ───────────────────────────────────────────────────────────────────


def test_signup_returns_user_without_password_hash(client: httpx.Client) -> None:
    r = client.post("/auth/signup", json={"email": "s1@test.com", "password": PASSWORD})
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "s1@test.com"
    assert body["role"] == "OWNER"  # 첫 사용자(admin fixture)가 아니므로 OWNER
    assert body["groups"] == []
    assert "password_hash" not in body
    assert "password" not in body


def test_signup_duplicate_email_is_409(client: httpx.Client, admin: Actor) -> None:
    r = client.post("/auth/signup", json={"email": admin.email, "password": PASSWORD})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


@pytest.mark.parametrize(
    ("payload", "bad_field"),
    [
        ({"email": "not-an-email", "password": PASSWORD}, "email"),
        ({"email": "s2@test.com", "password": "short"}, "password"),
        ({"password": PASSWORD}, "email"),
    ],
)
def test_signup_validation_is_422(client: httpx.Client, payload: dict[str, str], bad_field: str) -> None:
    r = client.post("/auth/signup", json=payload)
    assert r.status_code == 422
    assert any(e["loc"][-1] == bad_field for e in r.json()["detail"])


# ── login ────────────────────────────────────────────────────────────────────


def test_login_wrong_password_and_unknown_email_look_identical(client: httpx.Client, admin: Actor) -> None:
    wrong = client.post("/auth/login", json={"email": admin.email, "password": "nope-nope"})
    unknown = client.post("/auth/login", json={"email": "ghost@test.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()  # 가입 여부를 흘리지 않는다
    assert "set-cookie" not in wrong.headers


def test_login_sets_httponly_cookie_and_hides_token_from_body(client: httpx.Client, admin: Actor) -> None:
    r = client.post("/auth/login", json={"email": admin.email, "password": PASSWORD})
    client.cookies.clear()
    assert r.status_code == 200
    assert "access_token" not in r.json()
    cookie = r.headers["set-cookie"]
    assert cookie.startswith("access_token=")
    for flag in ("HttpOnly", "SameSite=lax", "Path=/"):
        assert flag in cookie
    assert "Secure" not in cookie  # COOKIE_SECURE=false (로컬)


# ── me / logout ──────────────────────────────────────────────────────────────


def test_me_requires_cookie(client: httpx.Client) -> None:
    r = client.get("/auth/me")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_me_with_cookie(client: httpx.Client, writer: Actor) -> None:
    r = client.get("/auth/me", headers=writer.headers)
    assert r.status_code == 200
    assert r.json()["email"] == writer.email
    assert r.json()["role"] == "GROUP_WRITER"


def test_me_accepts_bearer_header_fallback(client: httpx.Client, writer: Actor) -> None:
    token = writer.headers["Cookie"].removeprefix("access_token=")
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_logout_clears_cookie(client: httpx.Client) -> None:
    r = client.post("/auth/logout")
    assert r.status_code == 204
    cookie = r.headers["set-cookie"].lower()
    assert "access_token=" in cookie
    assert "max-age=0" in cookie or "expires=" in cookie


# ── token validation ─────────────────────────────────────────────────────────


def _encode(payload: dict[str, Any], secret: str) -> str:
    """테스트용 토큰 제조. PyJWT 의 느슨한 타입은 여기서만 무시한다."""
    return jwt.encode(payload, secret, algorithm="HS256")  # pyright: ignore[reportUnknownMemberType]


def _cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"access_token={token}"}


def test_expired_token_is_401(client: httpx.Client, admin: Actor) -> None:
    secret = get_settings().jwt_secret
    expired = _encode({"sub": admin.id, "exp": int(time.time()) - 5}, secret)
    r = client.get("/auth/me", headers=_cookie(expired))
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Token expired"


def test_forged_token_is_401(client: httpx.Client, admin: Actor) -> None:
    forged = _encode(
        {"sub": admin.id, "exp": int(time.time()) + 600}, "wrong-secret-but-long-enough-to-avoid-warning"
    )
    r = client.get("/auth/me", headers=_cookie(forged))
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "Invalid token"


def test_valid_token_for_deleted_user_is_401(client: httpx.Client) -> None:
    secret = get_settings().jwt_secret
    ghost = _encode({"sub": "000000000000000000000000", "exp": int(time.time()) + 600}, secret)
    r = client.get("/auth/me", headers=_cookie(ghost))
    assert r.status_code == 401
    assert r.json()["error"]["message"] == "User no longer exists"


def test_middleware_blocks_unknown_paths_before_routing(client: httpx.Client) -> None:
    assert client.get("/definitely/not/a/route").status_code == 401  # 404 가 아니라 401
