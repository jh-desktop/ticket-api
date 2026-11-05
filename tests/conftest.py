"""pytest 공용 설정과 fixture.

이 파일에 있는 fixture 는 tests/ 아래 모든 테스트에서 이름만 적으면 주입된다.
(FastAPI 의 Depends 와 같은 발상 — "필요하다" 고 인자에 적으면 pytest 가 만들어 넣어 준다.)

fixture 체인
    sync_db ─ client ─ admin ─┬─ writer
                              ├─ reader
                              ├─ owner
                              └─ owner_other
"""

import os

# ── 1. 환경 먼저 고정 (app 을 import 하기 전에!) ──────────────────────────────
# 환경변수는 .env 보다 우선이므로 테스트는 항상 별도 DB 를 쓴다.
os.environ["MONGO_DB_NAME"] = "ticket_api_test"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-at-least-32-bytes-long")
os.environ.setdefault("COOKIE_SECURE", "false")

from collections.abc import Callable, Iterator  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import Any, cast  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pymongo import MongoClient  # noqa: E402
from pymongo.database import Database  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import Document  # noqa: E402

get_settings.cache_clear()  # 혹시 먼저 만들어진 Settings 가 있으면 버린다

from app.server import app  # noqa: E402

PASSWORD = "password123"


@dataclass(frozen=True)
class Actor:
    """테스트에서 '이 사용자로 요청' 할 때 쓰는 묶음."""

    email: str
    id: str
    role: str
    headers: dict[str, str]  # {"Cookie": "access_token=..."}


# ── 2. DB ─────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def sync_db() -> Iterator[Database[Document]]:
    """테스트 DB 를 세션 시작 시 비우고, 끝나면 통째로 지운다.

    앱은 AsyncMongoClient 를 쓰지만 정리 작업은 동기 MongoClient 로 한다 —
    TestClient 의 이벤트 루프와 섞이지 않아서 단순하다.
    """
    settings = get_settings()
    assert settings.mongo_db_name == "ticket_api_test", "테스트가 실제 DB 를 가리키고 있다!"
    mongo: MongoClient[Document] = MongoClient(settings.mongo_uri)
    mongo.drop_database(settings.mongo_db_name)
    yield mongo[settings.mongo_db_name]
    mongo.drop_database(settings.mongo_db_name)
    mongo.close()


@pytest.fixture(autouse=True)
def clean_collections(sync_db: Database[Document]) -> None:
    """모든 테스트 전에 티켓·감사로그를 비운다. 사용자는 세션 동안 유지(가입·로그인 비용 절약)."""
    sync_db["tickets"].delete_many({})
    sync_db["audit_logs"].delete_many({})


# ── 3. 클라이언트 ─────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def client(sync_db: Database[Document]) -> Iterator[httpx.Client]:
    """세션당 하나. `with` 가 lifespan(connect_db → ... → close_db) 을 실행한다.

    여러 개 만들면 앱의 Mongo 클라이언트가 서로 다른 이벤트 루프에 묶여 깨진다.
    쿠키 저장소는 쓰지 않고(사용자마다 섞이므로) Actor.headers 로 매 요청에 명시한다.

    타입을 httpx.Client 로 적는 이유: starlette 1.10 은 타입 검사 시 httpx2 를 기대해서 TestClient 가
    Unknown 으로 잡힌다. TestClient 는 httpx.Client 의 하위 클래스이고 테스트는 그 메서드만 쓰므로 안전하다.
    """
    with cast(httpx.Client, TestClient(app)) as c:  # pyright: ignore[reportUnknownArgumentType]
        c.cookies.clear()
        yield c


# ── 4. 사용자 (역할별) ─────────────────────────────────────────────────────────


def _login(client: httpx.Client, email: str) -> dict[str, str]:
    r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    token = client.cookies.get("access_token")
    client.cookies.clear()  # 클라이언트 전역 쿠키에 남기지 않는다
    assert token
    return {"Cookie": f"access_token={token}"}


def _signup(client: httpx.Client, email: str) -> dict[str, str]:
    r = client.post("/auth/signup", json={"email": email, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return r.json()


def _make_actor(client: httpx.Client, admin: Actor, email: str, role: str, groups: list[str]) -> Actor:
    user = _signup(client, email)
    r = client.patch(f"/users/{user['id']}/role", json={"role": role, "groups": groups}, headers=admin.headers)
    assert r.status_code == 200, r.text
    return Actor(email=email, id=user["id"], role=role, headers=_login(client, email))


@pytest.fixture(scope="session", autouse=True)
def admin(client: httpx.Client) -> Actor:
    """빈 DB 의 첫 가입자 → ADMIN (부트스트랩 규칙을 그대로 이용).

    autouse: 어떤 테스트가 먼저 돌든 '첫 가입자' 자리는 항상 이 fixture 가 차지해야 한다.
    (안 그러면 test_auth 의 임의 가입 테스트가 먼저 돌아 그 사용자가 ADMIN 이 된다)
    """
    user = _signup(client, "admin@test.com")
    assert user["role"] == "ADMIN"
    return Actor(email=user["email"], id=user["id"], role="ADMIN", headers=_login(client, user["email"]))


@pytest.fixture(scope="session")
def writer(client: httpx.Client, admin: Actor) -> Actor:
    return _make_actor(client, admin, "writer@test.com", "GROUP_WRITER", ["backend"])


@pytest.fixture(scope="session")
def reader(client: httpx.Client, admin: Actor) -> Actor:
    return _make_actor(client, admin, "reader@test.com", "GROUP_READER", ["backend"])


@pytest.fixture(scope="session")
def owner(client: httpx.Client, admin: Actor) -> Actor:
    return _make_actor(client, admin, "owner@test.com", "OWNER", ["backend"])


@pytest.fixture(scope="session")
def owner_other(client: httpx.Client, admin: Actor) -> Actor:
    """다른 그룹(mobile)의 OWNER. 스코프 밖 접근을 검증할 때 쓴다."""
    return _make_actor(client, admin, "owner-other@test.com", "OWNER", ["mobile"])


# ── 5. 자주 쓰는 도우미 ────────────────────────────────────────────────────────


MakeTicket = Callable[..., dict[str, Any]]


@pytest.fixture
def make_ticket(client: httpx.Client) -> MakeTicket:
    """make_ticket(actor, title=..., group_id=...) → 생성된 티켓 dict."""

    def _make(actor: Actor, *, title: str = "ticket", group_id: str = "backend", description: str | None = None) -> dict[str, Any]:
        r = client.post(
            "/tickets",
            json={"title": title, "group_id": group_id, "description": description},
            headers=actor.headers,
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _make
