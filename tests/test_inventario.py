from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_crud_inventario_semaforo_y_trazabilidad_mermas():
    sufijo = uuid4().hex[:6]

    with TestClient(app) as client:
        usuarios = client.get("/api/v1/auth/usuarios").json()
        admin = next(u for u in usuarios if u["username"] == "admin")
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        ).status_code == 200

        # Asegurar un cajero activo para validar permisos
        client.post(
            "/api/v1/auth/usuarios",
            json={
                "nombre": "Cajero Inv",
                "username": "cajero_inv",
                "pin": "5678",
                "rol": "CAJERO",
            },
        )
        usuarios = client.get("/api/v1/auth/usuarios").json()
        cajero = next(u for u in usuarios if u["username"] == "cajero_inv")

        # 1. Crear categoria rapida y validar duplicado
        cat_nombre = f"Snacks {sufijo}"
        res_cat = client.post(
            "/api/v1/inventario/categorias",
            json={"nombre": cat_nombre},
        )
        assert res_cat.status_code == 201
        cat_id = res_cat.json()["id"]

        res_cat_dup = client.post(
            "/api/v1/inventario/categorias",
            json={"nombre": cat_nombre.lower()},
        )
        assert res_cat_dup.status_code == 400

        # 2. Crear producto sin proveedor con stock inicial 10 -> movimiento ENTRADA automatico
        venc_por_vencer = (date.today() + timedelta(days=3)).isoformat()
        res_prod = client.post(
            "/api/v1/inventario/productos",
            json={
                "nombre": f"Papas Fritas {sufijo}",
                "codigo_barras": f"780{sufijo}",
                "categoria_id": cat_id,
                "proveedor_id": None,
                "unidad": "UN",
                "precio_costo": 650,
                "precio_venta": 1100,
                "stock_actual": 10,
                "stock_minimo": 4,
                "fecha_vencimiento": venc_por_vencer,
            },
        )
        assert res_prod.status_code == 201
        prod = res_prod.json()
        prod_id = prod["id"]
        assert prod["proveedor_id"] is None
        assert prod["estado_vencimiento"] == "POR_VENCER"
        assert prod["bloqueado_venta"] is False

        movs_inicial = client.get(
            f"/api/v1/inventario/movimientos?producto_id={prod_id}"
        ).json()
        assert len(movs_inicial) == 1
        assert movs_inicial[0]["tipo"] == "ENTRADA"
        assert movs_inicial[0]["stock_nuevo"] == 10.0
        assert movs_inicial[0]["motivo"] == "Stock inicial"

        # 3. Editar producto y probar estados de semaforo (VENCIDO y OPTIMO)
        venc_pasado = (date.today() - timedelta(days=2)).isoformat()
        res_edit_vencido = client.put(
            f"/api/v1/inventario/productos/{prod_id}",
            json={
                "nombre": f"Papas Fritas {sufijo} Edit",
                "codigo_barras": f"780{sufijo}",
                "categoria_id": cat_id,
                "proveedor_id": None,
                "unidad": "UN",
                "precio_costo": 700,
                "precio_venta": 1200,
                "stock_minimo": 4,
                "fecha_vencimiento": venc_pasado,
            },
        )
        assert res_edit_vencido.status_code == 200
        assert res_edit_vencido.json()["estado_vencimiento"] == "VENCIDO"
        assert res_edit_vencido.json()["bloqueado_venta"] is True

        venc_optimo = (date.today() + timedelta(days=30)).isoformat()
        res_edit_optimo = client.put(
            f"/api/v1/inventario/productos/{prod_id}",
            json={
                "nombre": f"Papas Fritas {sufijo} Edit",
                "codigo_barras": f"780{sufijo}",
                "categoria_id": cat_id,
                "proveedor_id": None,
                "unidad": "UN",
                "precio_costo": 700,
                "precio_venta": 1200,
                "stock_minimo": 4,
                "fecha_vencimiento": venc_optimo,
            },
        )
        assert res_edit_optimo.status_code == 200
        assert res_edit_optimo.json()["estado_vencimiento"] == "OPTIMO"
        assert res_edit_optimo.json()["bloqueado_venta"] is False

        # 4. Admin registra ENTRADA (+5 -> 15) y AJUSTE (= 12)
        res_ent = client.post(
            f"/api/v1/inventario/productos/{prod_id}/movimientos",
            json={"tipo": "ENTRADA", "cantidad": 5, "motivo": "Compra en feria"},
        )
        assert res_ent.status_code == 201
        assert res_ent.json()["stock_nuevo"] == 15.0

        res_adj = client.post(
            f"/api/v1/inventario/productos/{prod_id}/movimientos",
            json={"tipo": "AJUSTE", "cantidad": 12, "motivo": "Conteo fisico mensual"},
        )
        assert res_adj.status_code == 201
        assert res_adj.json()["stock_anterior"] == 15.0
        assert res_adj.json()["stock_nuevo"] == 12.0
        assert res_adj.json()["cantidad"] == -3.0

        # 5. Cambiar a CAJERO: puede consultar y registrar MERMA, pero no CRUD ni ENTRADA/AJUSTE
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": cajero["id"], "pin": "5678"},
        ).status_code == 200

        assert client.get("/api/v1/inventario/resumen").status_code == 200
        assert client.post(
            "/api/v1/inventario/productos",
            json={
                "nombre": "No permitido",
                "precio_venta": 500,
            },
        ).status_code == 403
        assert client.post(
            f"/api/v1/inventario/productos/{prod_id}/movimientos",
            json={"tipo": "ENTRADA", "cantidad": 2, "motivo": "Intento cajero"},
        ).status_code == 403
        assert client.post(
            f"/api/v1/inventario/productos/{prod_id}/movimientos",
            json={"tipo": "AJUSTE", "cantidad": 5, "motivo": "Intento cajero"},
        ).status_code == 403

        res_merma = client.post(
            f"/api/v1/inventario/productos/{prod_id}/movimientos",
            json={"tipo": "MERMA", "cantidad": 2, "motivo": "Envase danado"},
        )
        assert res_merma.status_code == 201
        assert res_merma.json()["stock_anterior"] == 12.0
        assert res_merma.json()["stock_nuevo"] == 10.0

        # 6. Volver a ADMIN, desactivar producto y validar filtro incluir_inactivos
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        ).status_code == 200

        res_off = client.patch(
            f"/api/v1/inventario/productos/{prod_id}/estado",
            json={"activo": False},
        )
        assert res_off.status_code == 200
        assert res_off.json()["activo"] is False

        activos = client.get(f"/api/v1/inventario/productos?q={sufijo}").json()
        assert all(p["id"] != prod_id for p in activos)

        todos = client.get(
            f"/api/v1/inventario/productos?q={sufijo}&incluir_inactivos=true"
        ).json()
        assert any(p["id"] == prod_id and p["activo"] is False for p in todos)


def test_lotes_multiples_fefo_y_merma_por_lote():
    sufijo = uuid4().hex[:6]

    with TestClient(app) as client:
        usuarios = client.get("/api/v1/auth/usuarios").json()
        admin = next(u for u in usuarios if u["username"] == "admin")
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        ).status_code == 200

        # Asegurar caja abierta para vender en POS
        if client.get("/api/v1/pos/caja-actual").json() is None:
            assert (
                client.post("/api/v1/pos/caja/abrir", json={"fondo_inicial": 10000}).status_code
                == 201
            )

        # 1. Crear producto perecible con 5 unidades que vencen en 3 dias (POR_VENCER)
        venc_cercano = (date.today() + timedelta(days=3)).isoformat()
        venc_lejano = (date.today() + timedelta(days=20)).isoformat()
        venc_pasado = (date.today() - timedelta(days=2)).isoformat()

        res_prod = client.post(
            "/api/v1/inventario/productos",
            json={
                "nombre": f"Yogurt Pack {sufijo}",
                "codigo_barras": f"781{sufijo}",
                "unidad": "UN",
                "precio_costo": 250,
                "precio_venta": 450,
                "stock_actual": 5,
                "stock_minimo": 3,
                "fecha_vencimiento": venc_cercano,
            },
        )
        assert res_prod.status_code == 201
        prod_id = res_prod.json()["id"]

        # 2. Agregar nueva tanda de 10 unidades con fecha lejana -> 2 tandas activas, total 15
        res_ent = client.post(
            f"/api/v1/inventario/productos/{prod_id}/movimientos",
            json={
                "tipo": "ENTRADA",
                "cantidad": 10,
                "motivo": "Reposicion semanal",
                "fecha_vencimiento": venc_lejano,
            },
        )
        assert res_ent.status_code == 201
        assert res_ent.json()["stock_nuevo"] == 15.0

        prod_inv = client.get(f"/api/v1/inventario/productos?q={sufijo}").json()[0]
        assert len(prod_inv["lotes"]) == 2
        assert prod_inv["stock_actual"] == 15.0
        assert prod_inv["estado_vencimiento"] == "POR_VENCER"

        # 3. Vender 7 unidades en POS -> FEFO agota tanda +3d y deja 8 en tanda +20d -> OPTIMO
        res_venta = client.post(
            "/api/v1/pos/ventas",
            json={
                "metodo_pago": "EFECTIVO",
                "monto_recibido": 10000,
                "items": [{"producto_id": prod_id, "cantidad": 7}],
            },
        )
        assert res_venta.status_code == 201

        prod_pos_despues = client.get(f"/api/v1/pos/productos?q={sufijo}").json()[0]
        assert prod_pos_despues["stock_actual"] == 8.0
        assert prod_pos_despues["estado_vencimiento"] == "OPTIMO"
        assert prod_pos_despues["bloqueado_venta"] is False

        # 4. Ingresar tanda vencida de 3 unidades -> vendible sigue siendo 8, vencido 3, total 11
        res_venc = client.post(
            f"/api/v1/inventario/productos/{prod_id}/movimientos",
            json={
                "tipo": "ENTRADA",
                "cantidad": 3,
                "motivo": "Tanda hallada al fondo",
                "fecha_vencimiento": venc_pasado,
            },
        )
        assert res_venc.status_code == 201

        prod_con_vencido = client.get(f"/api/v1/inventario/productos?q={sufijo}").json()[0]
        assert prod_con_vencido["stock_actual"] == 11.0
        assert prod_con_vencido["stock_vendible"] == 8.0
        assert prod_con_vencido["stock_vencido"] == 3.0
        assert prod_con_vencido["bloqueado_venta"] is False

        # POS no permite vender 9 (solo 8 vigentes), pero si permite vender 1
        assert (
            client.post(
                "/api/v1/pos/ventas",
                json={
                    "metodo_pago": "EFECTIVO",
                    "monto_recibido": 10000,
                    "items": [{"producto_id": prod_id, "cantidad": 9}],
                },
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/v1/pos/ventas",
                json={
                    "metodo_pago": "EFECTIVO",
                    "monto_recibido": 10000,
                    "items": [{"producto_id": prod_id, "cantidad": 1}],
                },
            ).status_code
            == 201
        )

        # 5. Dar de baja por merma especificamente la tanda vencida
        lote_vencido = next(l for l in prod_con_vencido["lotes"] if l["vencido"])
        res_merma = client.post(
            f"/api/v1/inventario/productos/{prod_id}/movimientos",
            json={
                "tipo": "MERMA",
                "cantidad": 3,
                "motivo": "Retiro de tanda vencida",
                "lote_id": lote_vencido["id"],
            },
        )
        assert res_merma.status_code == 201

        prod_final = client.get(f"/api/v1/inventario/productos?q={sufijo}").json()[0]
        assert prod_final["stock_vencido"] == 0.0
        assert prod_final["stock_actual"] == 7.0
        assert prod_final["stock_vendible"] == 7.0


def test_vista_html_inventario_protegida():
    with TestClient(app) as client:
        # 1. Sin sesion redirige a /login
        res_anon = client.get("/inventario", follow_redirects=False)
        assert res_anon.status_code == 302
        assert res_anon.headers["location"] == "/login"

        # 2. CAJERO accede a /inventario sin boton de crear producto
        usuarios = client.get("/api/v1/auth/usuarios").json()
        admin = next(u for u in usuarios if u["username"] == "admin")
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        ).status_code == 200

        client.post(
            "/api/v1/auth/usuarios",
            json={
                "nombre": "Cajero Vista Inv",
                "username": "cajero_inv_html",
                "pin": "5678",
                "rol": "CAJERO",
            },
        )
        usuarios = client.get("/api/v1/auth/usuarios").json()
        cajero = next(u for u in usuarios if u["username"] == "cajero_inv_html")

        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": cajero["id"], "pin": "5678"},
        ).status_code == 200
        res_cajero = client.get("/inventario")
        assert res_cajero.status_code == 200
        assert "Inventario y Semaforo" in res_cajero.text
        assert "btn-nuevo-producto" not in res_cajero.text

        # 3. ADMIN ve /inventario con boton Nuevo producto
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        ).status_code == 200
        res_admin = client.get("/inventario")
        assert res_admin.status_code == 200
        assert "btn-nuevo-producto" in res_admin.text
