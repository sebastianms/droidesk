from fastapi.testclient import TestClient


def test_health_responds_ok_status_code(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200


def test_health_reports_ok_status(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.json() == {"status": "ok"}
