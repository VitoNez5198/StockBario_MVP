"""Prueba base de salud del sistema (Sprint 1)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthcheck_ok():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "StockBarrio"
    assert data["database"] in {"sqlite", "postgresql"}
