import httpx


def test_health_is_public_and_reports_test_db(client: httpx.Client) -> None:
    r = client.get("/health")  # 쿠키 없음 — _NO_AUTH_PATHS
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ticket_api_test"  # 실제 DB 가 아닌지 한 번 더 확인


def test_docs_are_public(client: httpx.Client) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
