from fastapi.testclient import TestClient

from app.main import app


def test_flujo_login_roles_y_logout():
    with TestClient(app) as client:
        res_lista = client.get("/api/v1/auth/usuarios")
        assert res_lista.status_code == 200
        usuarios = res_lista.json()
        assert len(usuarios) >= 1
        admin = next(u for u in usuarios if u["username"] == "admin")
        assert "pin_hash" not in admin

        # PIN incorrecto debe fallar con 401
        res_mal = client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "9999"},
        )
        assert res_mal.status_code == 401

        # Login correcto como ADMIN
        res_ok = client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        )
        assert res_ok.status_code == 200
        assert res_ok.json()["usuario"]["rol"] == "ADMIN"

        # Consultar sesion actual
        res_me = client.get("/api/v1/auth/me")
        assert res_me.status_code == 200
        assert res_me.json()["username"] == "admin"

        # Admin puede crear un cajero (o reutilizarlo si ya existe)
        res_cajero = client.post(
            "/api/v1/auth/usuarios",
            json={
                "nombre": "Cajero Turno",
                "username": "cajero_test",
                "pin": "4321",
                "rol": "CAJERO",
            },
        )
        assert res_cajero.status_code in (201, 409)

        usuarios = client.get("/api/v1/auth/usuarios").json()
        cajero = next(u for u in usuarios if u["username"] == "cajero_test")

        # Cambiar sesion a CAJERO
        res_login_cajero = client.post(
            "/api/v1/auth/login",
            json={"usuario_id": cajero["id"], "pin": "4321"},
        )
        assert res_login_cajero.status_code == 200

        # Cajero NO puede crear usuarios (403)
        res_prohibido = client.post(
            "/api/v1/auth/usuarios",
            json={
                "nombre": "Otro Usuario",
                "username": "otro_test",
                "pin": "5678",
                "rol": "CAJERO",
            },
        )
        assert res_prohibido.status_code == 403

        # Logout invalida sesion
        res_out = client.post("/api/v1/auth/logout")
        assert res_out.status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401
