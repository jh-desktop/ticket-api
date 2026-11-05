"""역할 4종 × 행위 매트릭스. 각 테스트는 '누가 / 무엇을 / 어떤 결과' 한 줄로 읽히게 쓴다."""



import pytest
import httpx

from tests.conftest import Actor, MakeTicket




@pytest.fixture
def actors(admin: Actor, writer: Actor, reader: Actor, owner: Actor, owner_other: Actor) -> dict[str, Actor]:
    return {"admin": admin, "writer": writer, "reader": reader, "owner": owner, "owner_other": owner_other}


# ── 인증 자체 ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/tickets"), ("POST", "/tickets"), ("GET", "/users"), ("GET", "/audit-logs"), ("GET", "/auth/me")],
)
def test_everything_requires_login(client: httpx.Client, method: str, path: str) -> None:
    r = client.request(method, path, json={})
    assert r.status_code == 401


# ── 생성 ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("who", "group", "expected"),
    [
        ("admin", "anything", 201),  # ADMIN 은 어디든
        ("writer", "backend", 201),  # 내 그룹
        ("writer", "mobile", 403),  # 남의 그룹
        ("owner", "backend", 201),  # 내 그룹
        ("owner", "mobile", 403),  # 남의 그룹
        ("reader", "backend", 403),  # READER 는 생성 불가
    ],
)
def test_create_permissions(client: httpx.Client, actors: dict[str, Actor], who: str, group: str, expected: int) -> None:
    r = client.post("/tickets", json={"title": "t", "group_id": group}, headers=actors[who].headers)
    assert r.status_code == expected, r.text
    if expected == 403:
        assert r.json()["error"]["code"] == "forbidden"


# ── 조회 범위 (scope_filter) ──────────────────────────────────────────────────


def test_list_scope_per_role(client: httpx.Client, actors: dict[str, Actor], make_ticket: MakeTicket) -> None:
    make_ticket(actors["owner"], title="owner-backend", group_id="backend")
    make_ticket(actors["writer"], title="writer-backend", group_id="backend")
    make_ticket(actors["owner_other"], title="other-mobile", group_id="mobile")

    def titles(a: Actor) -> set[str]:
        return {t["title"] for t in client.get("/tickets?limit=100", headers=a.headers).json()}

    assert titles(actors["admin"]) == {"owner-backend", "writer-backend", "other-mobile"}
    assert titles(actors["writer"]) == {"owner-backend", "writer-backend"}  # 그룹 전체
    assert titles(actors["reader"]) == {"owner-backend", "writer-backend"}  # 그룹 전체 (읽기만)
    assert titles(actors["owner"]) == {"owner-backend"}  # 내 것만
    assert titles(actors["owner_other"]) == {"other-mobile"}


def test_ticket_outside_scope_is_404_not_403(client: httpx.Client, owner: Actor, owner_other: Actor, make_ticket: MakeTicket) -> None:
    t = make_ticket(owner)
    r = client.get(f"/tickets/{t['id']}", headers=owner_other.headers)
    assert r.status_code == 404  # 존재 여부를 흘리지 않는다
    assert client.patch(f"/tickets/{t['id']}", json={"title": "x"}, headers=owner_other.headers).status_code == 404
    assert client.delete(f"/tickets/{t['id']}", headers=owner_other.headers).status_code == 404


def test_same_group_reader_can_see_but_not_touch(client: httpx.Client, owner: Actor, reader: Actor, make_ticket: MakeTicket) -> None:
    t = make_ticket(owner)
    assert client.get(f"/tickets/{t['id']}", headers=reader.headers).status_code == 200
    assert client.patch(f"/tickets/{t['id']}", json={"title": "x"}, headers=reader.headers).status_code == 403
    assert client.delete(f"/tickets/{t['id']}", headers=reader.headers).status_code == 403


# ── 수정·삭제 ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("creator", "editor", "expected"),
    [
        ("owner", "owner", 200),  # 내 것
        ("owner", "admin", 200),  # 관리자는 누구 것이든
        ("owner", "writer", 403),  # 같은 그룹 WRITER 라도 남의 것은 못 고침
        ("writer", "writer", 200),
    ],
)
def test_edit_permissions(
    client: httpx.Client, actors: dict[str, Actor], make_ticket: MakeTicket, creator: str, editor: str, expected: int
) -> None:
    t = make_ticket(actors[creator])
    r = client.patch(f"/tickets/{t['id']}", json={"title": "edited"}, headers=actors[editor].headers)
    assert r.status_code == expected, r.text


# ── 승인·반려 ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("creator", "approver", "expected", "why"),
    [
        ("owner", "admin", 200, "ADMIN"),
        ("owner", "writer", 200, "같은 그룹 WRITER"),
        ("owner", "owner", 403, "OWNER 는 역할 게이트에서 막힘"),
        ("owner", "reader", 403, "READER 도 역할 게이트"),
        ("owner_other", "writer", 404, "다른 그룹 티켓은 보이지도 않음"),
    ],
)
def test_approve_permissions(
    client: httpx.Client, actors: dict[str, Actor], make_ticket: MakeTicket, creator: str, approver: str, expected: int, why: str
) -> None:
    group = "mobile" if creator == "owner_other" else "backend"
    t = make_ticket(actors[creator], group_id=group)
    r = client.post(f"/tickets/{t['id']}/approve", headers=actors[approver].headers)
    assert r.status_code == expected, f"{why}: {r.text}"


# ── 관리자 전용 ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/users", "/audit-logs"])
@pytest.mark.parametrize("who", ["writer", "reader", "owner"])
def test_admin_only_endpoints(client: httpx.Client, actors: dict[str, Actor], path: str, who: str) -> None:
    assert client.get(path, headers=actors[who].headers).status_code == 403
    assert client.get(path, headers=actors["admin"].headers).status_code == 200


def test_only_admin_can_assign_roles(client: httpx.Client, actors: dict[str, Actor]) -> None:
    target = actors["reader"].id
    r = client.patch(f"/users/{target}/role", json={"role": "ADMIN", "groups": []}, headers=actors["writer"].headers)
    assert r.status_code == 403  # 권한 상승 시도 차단
    r = client.get("/auth/me", headers=actors["reader"].headers)
    assert r.json()["role"] == "GROUP_READER"  # 그대로
