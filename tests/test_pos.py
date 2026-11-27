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


def test_flujo_pos_caja_bloqueo_venta_y_anulacion():
    with TestClient(app) as client:
        _cerrar_cajas_abiertas()

        usuarios = client.get("/api/v1/auth/usuarios").json()
        admin = next(u for u in usuarios if u["username"] == "admin")
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        ).status_code == 200

        # Asegurar un cajero activo para probar anulacion como CAJERO
        client.post(
            "/api/v1/auth/usuarios",
            json={
                "nombre": "Cajero POS",
                "username": "cajero_pos",
                "pin": "4321",
                "rol": "CAJERO",
            },
        )
        usuarios = client.get("/api/v1/auth/usuarios").json()
        cajero = next(u for u in usuarios if u["username"] == "cajero_pos")
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": cajero["id"], "pin": "4321"},
        ).status_code == 200

        productos = client.get("/api/v1/pos/productos").json()
        assert len(productos) >= 6

        prod_optimo = next(p for p in productos if not p["bloqueado_venta"])
        prod_vencido = next(p for p in productos if p["estado_vencimiento"] == "VENCIDO")

        # 1. Intentar vender sin caja abierta -> 400
        res_sin_caja = client.post(
            "/api/v1/pos/ventas",
            json={
                "metodo_pago": "EFECTIVO",
                "monto_recibido": 10000,
                "items": [{"producto_id": prod_optimo["id"], "cantidad": 1}],
            },
        )
        assert res_sin_caja.status_code == 400

        # 2. Abrir caja con fondo inicial -> 201
        res_caja = client.post("/api/v1/pos/caja/abrir", json={"fondo_inicial": 20000})
        assert res_caja.status_code == 201
        assert res_caja.json()["estado"] == "ABIERTA"

        # 3. Intentar vender producto vencido -> 400
        res_vencido = client.post(
            "/api/v1/pos/ventas",
            json={
                "metodo_pago": "EFECTIVO",
                "monto_recibido": 10000,
                "items": [{"producto_id": prod_vencido["id"], "cantidad": 1}],
            },
        )
        assert res_vencido.status_code == 400

        # 4. Vender producto valido en efectivo
        stock_antes = prod_optimo["stock_actual"]
        total_esperado = prod_optimo["precio_venta"] * 2
        monto_recibido = total_esperado + 500
        res_venta = client.post(
            "/api/v1/pos/ventas",
            json={
                "metodo_pago": "EFECTIVO",
                "monto_recibido": monto_recibido,
                "items": [{"producto_id": prod_optimo["id"], "cantidad": 2}],
            },
        )
        assert res_venta.status_code == 201
        venta = res_venta.json()
        assert venta["total"] == total_esperado
        assert venta["vuelto"] == 500
        assert venta["estado"] == "COMPLETADA"

        # Verificar descuento de stock y presencia en historial
        prods_despues = client.get(
            "/api/v1/pos/productos",
            params={"q": prod_optimo["nombre"]},
        ).json()
        prod_despues = next(p for p in prods_despues if p["id"] == prod_optimo["id"])
        assert prod_despues["stock_actual"] == stock_antes - 2

        historial = client.get("/api/v1/pos/ventas").json()
        assert any(v["id"] == venta["id"] for v in historial)

        # 5. Anular venta como CAJERO y verificar reposicion de stock
        res_anular = client.post(f"/api/v1/pos/ventas/{venta['id']}/anular")
        assert res_anular.status_code == 200
        assert res_anular.json()["estado"] == "ANULADA"

        prods_final = client.get(
            "/api/v1/pos/productos",
            params={"q": prod_optimo["nombre"]},
        ).json()
        prod_final = next(p for p in prods_final if p["id"] == prod_optimo["id"])
        assert prod_final["stock_actual"] == stock_antes


def test_vista_html_pos_protegida():
    with TestClient(app) as client:
        # Sin sesion redirige a /login
        res_anon = client.get("/pos", follow_redirects=False)
        assert res_anon.status_code == 302
        assert res_anon.headers["location"] == "/login"

        # Con sesion carga la vista /pos
        usuarios = client.get("/api/v1/auth/usuarios").json()
        admin = next(u for u in usuarios if u["username"] == "admin")
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        ).status_code == 200

        res_pos = client.get("/pos")
        assert res_pos.status_code == 200
        assert "Meson (Cobro)" in res_pos.text
        assert "Historial del dia" in res_pos.text
        assert "Inventario" in res_pos.text
        assert "Libreta Fiados" in res_pos.text
        assert "Compras" in res_pos.text
        assert "Caja Z" in res_pos.text


def test_ticket_termico_80mm():
    with TestClient(app) as client:
        _cerrar_cajas_abiertas()

        usuarios = client.get("/api/v1/auth/usuarios").json()
        admin = next(u for u in usuarios if u["username"] == "admin")
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        ).status_code == 200

        assert client.post("/api/v1/pos/caja/abrir", json={"fondo_inicial": 10000}).status_code == 201
        productos = client.get("/api/v1/pos/productos").json()
        prod = next(p for p in productos if not p["bloqueado_venta"])

        res_venta = client.post(
            "/api/v1/pos/ventas",
            json={
                "metodo_pago": "EFECTIVO",
                "monto_recibido": prod["precio_venta"],
                "items": [{"producto_id": prod["id"], "cantidad": 1}],
            },
        )
        assert res_venta.status_code == 201
        venta = res_venta.json()

        res_ticket = client.get(f"/pos/ticket/{venta['id']}")
        assert res_ticket.status_code == 200
        assert venta["folio"] in res_ticket.text
        assert "COMPROBANTE INTERNO" in res_ticket.text
        assert "80mm" in res_ticket.text

        res_embed = client.get(f"/pos/ticket/{venta['id']}", params={"embed": "1"})
        assert res_embed.status_code == 200
        assert venta["folio"] in res_embed.text
