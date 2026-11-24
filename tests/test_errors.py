from fastapi.testclient import TestClient

from app.main import app


def test_formato_errores_controlados():
    with TestClient(app) as client:
        # 401 sin sesion
        res_401 = client.get("/api/v1/auth/me")
        assert res_401.status_code == 401
        body_401 = res_401.json()
        assert body_401["codigo"] == 401
        assert "error" in body_401

        # 422 PIN invalido (menos de 4 digitos)
        res_422 = client.post(
            "/api/v1/auth/login",
            json={"usuario_id": 1, "pin": "12"},
        )
        assert res_422.status_code == 422
        body_422 = res_422.json()
        assert body_422["codigo"] == 422
        assert body_422["error"] == "Datos de entrada invalidos"
        assert len(body_422["detalles"]) >= 1
