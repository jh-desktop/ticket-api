import httpx

from tests.conftest import Actor, MakeTicket


def test_scheduler_snapshot_needs_no_auth_and_counts_tickets(
    client: httpx.Client, admin: Actor, writer: Actor, owner_other: Actor, make_ticket: MakeTicket
) -> None:
    a = make_ticket(writer, group_id="backend")
    make_ticket(writer, group_id="backend")
    b = make_ticket(owner_other, group_id="mobile")
    client.post(f"/tickets/{a['id']}/approve", headers=admin.headers)
    client.post(f"/tickets/{b['id']}/reject", headers=admin.headers)

    r = client.post("/scheduler/snapshots")  # 쿠키 없음 — _NO_AUTH_PREFIXES
    assert r.status_code == 201, r.text
    snap = r.json()
    assert snap["total"] == 3
    assert snap["by_status"] == {"open": 1, "approved": 1, "rejected": 1}
    assert snap["by_group"] == {"backend": 2, "mobile": 1}


def test_snapshot_fills_missing_statuses_with_zero(client: httpx.Client) -> None:
    snap = client.post("/scheduler/snapshots").json()
    assert snap["total"] == 0
    assert snap["by_status"] == {"open": 0, "approved": 0, "rejected": 0}
    assert snap["by_group"] == {}


def test_snapshot_history_is_admin_only_and_newest_first(client: httpx.Client, admin: Actor, writer: Actor, make_ticket: MakeTicket) -> None:
    client.post("/scheduler/snapshots")
    make_ticket(writer)
    client.post("/scheduler/snapshots")

    assert client.get("/snapshots", headers=writer.headers).status_code == 403
    assert client.get("/snapshots").status_code == 401

    r = client.get("/snapshots?limit=2", headers=admin.headers)
    assert r.status_code == 200
    newest, older = r.json()[0], r.json()[1]
    assert newest["total"] == 1 and older["total"] == 0
    assert newest["taken_at"] >= older["taken_at"]
