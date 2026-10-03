"""GET /api/v1/health: unauthenticated and cheap, because the CRM's worker polls it to resume delivery after an outage."""


def test_health_answers_without_a_login(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.get_json()["data"] == {"status": "ok", "database": "ok"}


def test_health_ignores_a_bad_token(client):
    assert client.get("/api/v1/health", headers={"Authorization": "Bearer not-a-token"}).status_code == 200
