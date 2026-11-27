from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def test_compras_sugeridas_proveedores_y_whatsapp():
    sufijo = uuid4().hex[:6]

    with TestClient(app) as client:
        usuarios = client.get("/api/v1/auth/usuarios").json()
        admin = next(u for u in usuarios if u["username"] == "admin")
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        ).status_code == 200

        client.post(
            "/api/v1/auth/usuarios",
            json={
                "nombre": "Cajero Compras",
                "username": "cajero_compras",
                "pin": "5678",
                "rol": "CAJERO",
            },
        )
        usuarios = client.get("/api/v1/auth/usuarios").json()
        cajero = next(u for u in usuarios if u["username"] == "cajero_compras")

        # 1. Crear proveedor y validar duplicado
        prov_nombre = f"Distribuidora {sufijo}"
        res_prov = client.post(
            "/api/v1/compras/proveedores",
            json={
                "nombre": prov_nombre,
                "telefono_whatsapp": "+56 9 8888 7777",
                "contacto": "Reparto martes",
            },
        )
        assert res_prov.status_code == 201
        prov_id = res_prov.json()["id"]

        assert (
            client.post(
                "/api/v1/compras/proveedores",
                json={"nombre": prov_nombre.lower()},
            ).status_code
            == 400
        )

        # 2. Producto con proveedor bajo minimo (stock=2, min=5 -> pedir 2*5-2 = 8)
        res_p1 = client.post(
            "/api/v1/inventario/productos",
            json={
                "nombre": f"Aceite 1L {sufijo}",
                "codigo_barras": f"783{sufijo}",
                "proveedor_id": prov_id,
                "unidad": "UN",
                "precio_costo": 1500,
                "precio_venta": 2200,
                "stock_actual": 2,
                "stock_minimo": 5,
            },
        )
        assert res_p1.status_code == 201

        # 3. Producto sin proveedor con stock vencido (stock=4 pero vencido -> vendible=0, min=3 -> pedir 6)
        venc_pasado = (date.today() - timedelta(days=1)).isoformat()
        res_p2 = client.post(
            "/api/v1/inventario/productos",
            json={
                "nombre": f"Mantequilla {sufijo}",
                "codigo_barras": f"784{sufijo}",
                "proveedor_id": None,
                "unidad": "UN",
                "precio_costo": 1800,
                "precio_venta": 2500,
                "stock_actual": 4,
                "stock_minimo": 3,
                "fecha_vencimiento": venc_pasado,
            },
        )
        assert res_p2.status_code == 201

        # 4. Consultar compras sugeridas -> valida formula, agrupacion y link WhatsApp
        sugeridas = client.get("/api/v1/compras/sugeridas").json()
        grupos = sugeridas["grupos"]

        grupo_prov = next(g for g in grupos if g["proveedor_id"] == prov_id)
        item_p1 = next(i for i in grupo_prov["items"] if sufijo in i["nombre"])
        assert item_p1["cantidad_sugerida"] == 8.0
        assert item_p1["subtotal_estimado"] == 12000
        assert "56988887777" in grupo_prov["whatsapp_url"]
        assert "Aceite" in grupo_prov["mensaje_whatsapp"]

        grupo_presencial = next(g for g in grupos if g["proveedor_id"] is None)
        item_p2 = next(i for i in grupo_presencial["items"] if sufijo in i["nombre"])
        assert item_p2["stock_vendible"] == 0.0
        assert item_p2["cantidad_sugerida"] == 6.0
        assert grupo_presencial["proveedor_nombre"] == "Compra presencial / Sin proveedor"

        # 5. Cajero puede consultar sugeridas, pero recibe 403 al mutar proveedores
        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": cajero["id"], "pin": "5678"},
        ).status_code == 200
        assert client.get("/api/v1/compras/sugeridas").status_code == 200
        assert (
            client.post(
                "/api/v1/compras/proveedores",
                json={"nombre": "Otro Proveedor"},
            ).status_code
            == 403
        )


def test_vista_html_compras_protegida():
    with TestClient(app) as client:
        res_anon = client.get("/compras", follow_redirects=False)
        assert res_anon.status_code == 302
        assert res_anon.headers["location"] == "/login"

        usuarios = client.get("/api/v1/auth/usuarios").json()
        admin = next(u for u in usuarios if u["username"] == "admin")
        cajero = next(u for u in usuarios if u["username"] == "cajero_compras")

        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": cajero["id"], "pin": "5678"},
        ).status_code == 200
        res_caj = client.get("/compras")
        assert res_caj.status_code == 200
        assert "Compras Sugeridas WhatsApp" in res_caj.text
        assert "btn-nuevo-proveedor" not in res_caj.text

        assert client.post(
            "/api/v1/auth/login",
            json={"usuario_id": admin["id"], "pin": "1234"},
        ).status_code == 200
        res_adm = client.get("/compras")
        assert res_adm.status_code == 200
        assert "btn-nuevo-proveedor" in res_adm.text
