

import pytest
import httpx

from tests.conftest import Actor, MakeTicket



# ── create / read ────────────────────────────────────────────────────────────


def test_create_sets_defaults_and_owner(client: httpx.Client, writer: Actor) -> None:
    r = client.post("/tickets", json={"title": "login bug", "group_id": "backend"}, headers=writer.headers)
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "open"
    assert body["owner_id"] == writer.id  # 요청 본문이 아니라 로그인 사용자에서
    assert body["group_id"] == "backend"
    assert body["description"] is None
    assert set(body) == {"id", "title", "description", "status", "owner_id", "group_id", "created_at"}


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "group_id": "backend"},  # 빈 제목
        {"group_id": "backend"},  # 제목 없음
        {"title": "x"},  # 그룹 없음
        {"title": "x", "group_id": ""},  # 빈 그룹
    ],
)
def test_create_validation_is_422(client: httpx.Client, writer: Actor, payload: dict[str, str]) -> None:
    assert client.post("/tickets", json=payload, headers=writer.headers).status_code == 422


def test_get_by_id(client: httpx.Client, writer: Actor, make_ticket: MakeTicket) -> None:
    t = make_ticket(writer, title="one")
    r = client.get(f"/tickets/{t['id']}", headers=writer.headers)
    assert r.status_code == 200
    assert r.json()["title"] == "one"


@pytest.mark.parametrize("bad_id", ["abc", "123", "000000000000000000000000"])
def test_get_unknown_or_malformed_id_is_404(client: httpx.Client, writer: Actor, bad_id: str) -> None:
    r = client.get(f"/tickets/{bad_id}", headers=writer.headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_list_is_sorted_and_paginated(client: httpx.Client, writer: Actor, make_ticket: MakeTicket) -> None:
    for i in range(5):
        make_ticket(writer, title=f"t{i}")
    all_titles = [t["title"] for t in client.get("/tickets", headers=writer.headers).json()]
    assert all_titles == ["t0", "t1", "t2", "t3", "t4"]
    page2 = client.get("/tickets?skip=2&limit=2", headers=writer.headers).json()
    assert [t["title"] for t in page2] == ["t2", "t3"]
    assert client.get("/tickets?limit=0", headers=writer.headers).status_code == 422
    assert client.get("/tickets?limit=101", headers=writer.headers).status_code == 422


# ── update / delete ──────────────────────────────────────────────────────────


def test_patch_updates_only_sent_fields(client: httpx.Client, writer: Actor, make_ticket: MakeTicket) -> None:
    t = make_ticket(writer, title="orig", description="d1")
    r = client.patch(f"/tickets/{t['id']}", json={"description": "d2"}, headers=writer.headers)
    assert r.status_code == 200
    assert r.json()["title"] == "orig"
    assert r.json()["description"] == "d2"


def test_patch_cannot_change_status(client: httpx.Client, writer: Actor, make_ticket: MakeTicket) -> None:
    t = make_ticket(writer)
    r = client.patch(f"/tickets/{t['id']}", json={"status": "approved"}, headers=writer.headers)
    assert r.status_code == 200
    assert r.json()["status"] == "open"  # 모르는 필드는 무시된다 (TicketUpdate 에 없음)


def test_delete_then_404(client: httpx.Client, writer: Actor, make_ticket: MakeTicket) -> None:
    t = make_ticket(writer)
    assert client.delete(f"/tickets/{t['id']}", headers=writer.headers).status_code == 204
    assert client.get(f"/tickets/{t['id']}", headers=writer.headers).status_code == 404
    assert client.delete(f"/tickets/{t['id']}", headers=writer.headers).status_code == 404


# ── state transitions ────────────────────────────────────────────────────────


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_open_ticket_can_transition_once(client: httpx.Client, writer: Actor, make_ticket: MakeTicket, action: str) -> None:
    t = make_ticket(writer)
    r = client.post(f"/tickets/{t['id']}/{action}", headers=writer.headers)
    assert r.status_code == 200
    assert r.json()["status"] == f"{action}d" if action == "approve" else "rejected"


@pytest.mark.parametrize(("first", "second"), [("approve", "reject"), ("approve", "approve"), ("reject", "approve"), ("reject", "reject")])
def test_closed_ticket_rejects_further_transitions(
    client: httpx.Client, writer: Actor, make_ticket: MakeTicket, first: str, second: str
) -> None:
    t = make_ticket(writer)
    assert client.post(f"/tickets/{t['id']}/{first}", headers=writer.headers).status_code == 200
    r = client.post(f"/tickets/{t['id']}/{second}", headers=writer.headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "invalid_transition"


# ── audit trail ──────────────────────────────────────────────────────────────


def test_audit_trail_records_every_change_with_actor(
    client: httpx.Client, admin: Actor, writer: Actor, make_ticket: MakeTicket
) -> None:
    t = make_ticket(writer, title="v1", description="d1")
    client.patch(f"/tickets/{t['id']}", json={"title": "v2"}, headers=writer.headers)
    client.post(f"/tickets/{t['id']}/approve", headers=admin.headers)
    client.post(f"/tickets/{t['id']}/reject", headers=admin.headers)  # 409 → 기록되면 안 됨
    client.delete(f"/tickets/{t['id']}", headers=admin.headers)

    logs = client.get(f"/audit-logs?ticket_id={t['id']}", headers=admin.headers).json()
    assert [(l["action"], l["actor"]) for l in logs] == [
        ("ticket.deleted", admin.id),
        ("ticket.approved", admin.id),
        ("ticket.updated", writer.id),
        ("ticket.created", writer.id),
    ]
    created, updated, approved = logs[3], logs[2], logs[1]
    assert created["before"] is None and created["after"]["title"] == "v1"
    assert updated["before"] == {"title": "v1"} and updated["after"] == {"title": "v2"}
    assert approved["before"] == {"status": "open"} and approved["after"] == {"status": "approved"}
    assert logs[0]["after"] is None  # deleted
