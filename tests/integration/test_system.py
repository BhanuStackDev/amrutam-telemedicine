from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_readiness_endpoint_with_dependencies():
    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()

    assert body["status"] == "ready"
    assert body["dependencies"]["postgres"] == "ok"
    assert body["dependencies"]["redis"] == "ok"


def test_metrics_endpoint_exposes_prometheus_metrics():
    with TestClient(app) as client:
        client.get("/health")
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "python_info" in response.text


def test_required_api_schema_paths_exist():
    paths = app.openapi()["paths"]

    required_paths = {
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/doctors",
        "/api/v1/availability",
        "/api/v1/consultations/book",
        "/api/v1/prescriptions",
        "/api/v1/admin/analytics",
        "/api/v1/admin/audit-logs",
    }

    missing = required_paths.difference(paths)

    assert not missing, f"Missing required API paths: {sorted(missing)}"


def test_security_headers_are_present():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "permissions-policy" in response.headers
    assert "x-request-id" in response.headers
