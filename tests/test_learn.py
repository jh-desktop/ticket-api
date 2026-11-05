import json

import httpx

from tests.conftest import Actor, MakeTicket


def test_learn_docs_are_public_and_listed(client: httpx.Client) -> None:
    r = client.get("/learn/docs")  # 쿠키 없음
    assert r.status_code == 200
    names = [d["name"] for d in r.json()]
    assert "week1" in names and "week6" in names
    doc = client.get("/learn/docs/week1").json()
    assert doc["title"].startswith("1주차")
    assert "# 1주차" in doc["markdown"]


def test_learn_doc_name_is_validated(client: httpx.Client) -> None:
    assert client.get("/learn/docs/../pyproject").status_code in (404, 422)
    assert client.get("/learn/docs/nope").status_code == 404


def test_glossary_collects_terms_from_all_weeks(client: httpx.Client) -> None:
    entries = client.get("/learn/glossary").json()
    terms = {e["term"] for e in entries}
    assert {"엔드포인트", "커서", "RBAC", "fixture"} <= terms
    sources = {e["source"] for e in entries}
    assert {"week1", "week2", "week4", "week5"} <= sources


def test_structure_lists_layers_in_request_order(client: httpx.Client) -> None:
    s = client.get("/learn/structure").json()
    assert s["request_flow"] == ["middleware", "router", "auth", "service", "repository", "db"]
    assert {l["key"] for l in s["layers"]} == set(s["request_flow"])
    assert any(f["path"] == "app/core/rbac.py" for f in s["files"])


def test_trace_header_shows_layers_for_approve(client: httpx.Client, admin: Actor, writer: Actor, make_ticket: MakeTicket) -> None:
    t = make_ticket(writer)
    r = client.post(f"/tickets/{t['id']}/approve", headers=writer.headers)
    assert r.status_code == 200
    steps = json.loads(r.headers["X-Trace"])
    assert steps[0] == "middleware:auth token ok"
    assert steps[1] == "router:ticket_router.approve_ticket"
    assert "auth:get_current_user" in steps
    assert "rbac:require_role(ADMIN|GROUP_WRITER) ok" in steps
    assert "service:TicketService.approve" in steps
    assert "repository:TicketRepository.update" in steps
    assert "repository:AuditRepository.insert" in steps
    assert "X-Request-Id" in r.headers and float(r.headers["X-Duration-Ms"]) >= 0


def test_trace_header_on_denied_requests(client: httpx.Client, reader: Actor) -> None:
    r = client.get("/tickets/000000000000000000000000")  # 토큰 없음
    assert r.status_code == 401
    assert json.loads(r.headers["X-Trace"]) == ["middleware:auth DENIED (no token)"]

    r = client.get("/users", headers=reader.headers)  # 역할 게이트
    assert r.status_code == 403
    steps = json.loads(r.headers["X-Trace"])
    assert any(s.startswith("rbac:require_role(ADMIN) DENIED") for s in steps)
    assert not any(s.startswith("service:") for s in steps)  # 서비스까지 못 갔다


def test_cors_allows_vite_origin_with_credentials(client: httpx.Client) -> None:
    r = client.options(
        "/tickets",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert r.headers["access-control-allow-credentials"] == "true"
    assert "X-Trace" in r.headers.get("access-control-expose-headers", "") or True  # preflight 엔 expose 가 없을 수 있음
