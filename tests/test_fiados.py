from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import update

from app.core.database import SessionLocal
from app.main import app
from app.models import EstadoCaja, SesionCaja


def _cerrar_cajas_abiertas() -> None:
    with SessionLocal() as db:
        db.execute(
            update(SesionCaja)
            .where(SesionCaja.estado == EstadoCaja.ABIERTA.value)
            .values(estado=EstadoCaja.CERRADA.value)
        )
        db.commit()


def test_flujo_fiados_pos_abonos_y_permisos():
    sufijo = uuid4().hex[:6]

    with TestClient(app) as client:
        _cerrar_cajas_abiertas()

        usuarios = client.get("/api/v1/auth/usuarios").json()
        admin = next(u for u in usuarios if u["username"] == "admin")
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        ).status_code == 200

        client.post(
            "/api/v1/auth/usuarios",
            json={
                "nombre": "Cajero Fiados",
                "username": "cajero_fiados",
                "pin": "5678",
                "rol": "CAJERO",
            },
        )
        usuarios = client.get("/api/v1/auth/usuarios/admin").json()
        cajero = next(u for u in usuarios if u["username"] == "cajero_fiados")
        assert (
            client.patch(
                f"/api/v1/auth/usuarios/{cajero['id']}",
                json={"pin": "5678", "rol": "CAJERO", "activo": True},
            ).status_code
            == 200
        )

        # 1. Admin crea cliente con limite $5.000
        res_cli = client.post(
            "/api/v1/fiados/clientes",
            json={
                "nombre": f"Vecino Prueba {sufijo}",
                "rut_o_apodo": "Pasaje 1",
                "telefono": "+56911112222",
                "limite_credito": 5000,
            },
        )
        assert res_cli.status_code == 201
        cliente = res_cli.json()
        cli_id = cliente["id"]
        assert cliente["cupo_disponible"] == 5000

        # Admin crea un producto de $2.000 para probar fiado dentro y fuera de limite
        res_prod = client.post(
            "/api/v1/inventario/productos",
            json={
                "nombre": f"Producto Fiado {sufijo}",
                "codigo_barras": f"782{sufijo}",
                "unidad": "UN",
                "precio_costo": 1200,
                "precio_venta": 2000,
                "stock_actual": 10,
                "stock_minimo": 2,
            },
        )
        assert res_prod.status_code == 201
        prod_id = res_prod.json()["id"]

        # 2. Cambiar a CAJERO: no puede crear/editar/desactivar clientes -> 403
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": cajero["id"], "pin": "5678"},
        ).status_code == 200

        assert client.post(
            "/api/v1/fiados/clientes",
            json={"nombre": "No permitido", "limite_credito": 1000},
        ).status_code == 403
        assert client.put(
            f"/api/v1/fiados/clientes/{cli_id}",
            json={"nombre": "No permitido", "limite_credito": 9000},
        ).status_code == 403
        assert client.patch(
            f"/api/v1/fiados/clientes/{cli_id}/estado",
            json={"activo": False},
        ).status_code == 403

        # Abrir caja y cobrar venta FIADO por $4.000 (dentro del limite)
        assert client.post("/api/v1/pos/caja/abrir", json={"fondo_inicial": 10000}).status_code == 201

        res_fiado = client.post(
            "/api/v1/pos/ventas",
            json={
                "metodo_pago": "FIADO",
                "cliente_id": cli_id,
                "items": [{"producto_id": prod_id, "cantidad": 2}],
            },
        )
        assert res_fiado.status_code == 201

        # Venta fiada adicional de $2.000 excede el limite ($4.000 + $2.000 > $5.000) -> 400
        assert (
            client.post(
                "/api/v1/pos/ventas",
                json={
                    "metodo_pago": "FIADO",
                    "cliente_id": cli_id,
                    "items": [{"producto_id": prod_id, "cantidad": 1}],
                },
            ).status_code
            == 400
        )

        # 3. Intentar abonar con caja cerrada -> 400
        _cerrar_cajas_abiertas()
        assert (
            client.post(
                f"/api/v1/fiados/clientes/{cli_id}/abonos",
                json={"monto": 1000, "metodo_pago": "EFECTIVO"},
            ).status_code
            == 400
        )

        # Reabrir caja y registrar abono parcial de $1.500 como CAJERO
        assert client.post("/api/v1/pos/caja/abrir", json={"fondo_inicial": 10000}).status_code == 201

        assert (
            client.post(
                f"/api/v1/fiados/clientes/{cli_id}/abonos",
                json={"monto": 5000, "metodo_pago": "EFECTIVO"},
            ).status_code
            == 400
        )

        res_abono1 = client.post(
            f"/api/v1/fiados/clientes/{cli_id}/abonos",
            json={"monto": 1500, "metodo_pago": "TRANSFERENCIA", "observacion": "Primer pago"},
        )
        assert res_abono1.status_code == 201
        assert res_abono1.json()["deuda_restante"] == 2500

        # Verificar historial unificado (FIADO + ABONO)
        movs = client.get(f"/api/v1/fiados/clientes/{cli_id}/movimientos").json()
        tipos = {m["tipo"] for m in movs}
        assert "FIADO" in tipos
        assert "ABONO" in tipos

        # 4. Admin no puede desactivar cliente mientras tenga deuda -> 400
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        ).status_code == 200
        assert (
            client.patch(
                f"/api/v1/fiados/clientes/{cli_id}/estado",
                json={"activo": False},
            ).status_code
            == 400
        )

        # Saldar deuda completa ($2.500) y luego desactivar -> 200
        assert (
            client.post(
                f"/api/v1/fiados/clientes/{cli_id}/abonos",
                json={"monto": 2500, "metodo_pago": "EFECTIVO"},
            ).status_code
            == 201
        )
        res_off = client.patch(
            f"/api/v1/fiados/clientes/{cli_id}/estado",
            json={"activo": False},
        )
        assert res_off.status_code == 200
        assert res_off.json()["activo"] is False


def test_vista_html_fiados_protegida():
    with TestClient(app) as client:
        res_anon = client.get("/fiados", follow_redirects=False)
        assert res_anon.status_code == 302
        assert res_anon.headers["location"] == "/login"

        usuarios = client.get("/api/v1/auth/usuarios").json()
        admin = next(u for u in usuarios if u["username"] == "admin")
        cajero = next(u for u in usuarios if u["username"] == "cajero_fiados")

        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": cajero["id"], "pin": "5678"},
        ).status_code == 200
        res_caj = client.get("/fiados")
        assert res_caj.status_code == 200
        assert "Libreta de Fiados" in res_caj.text
        assert "btn-nuevo-cliente" not in res_caj.text

        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        ).status_code == 200
        res_adm = client.get("/fiados")
        assert res_adm.status_code == 200
        assert "btn-nuevo-cliente" in res_adm.text
