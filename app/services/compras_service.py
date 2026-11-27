import math
from decimal import Decimal
from urllib.parse import quote

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Almacen, Producto, Proveedor, Usuario
from app.schemas.compras import (
    ActualizarProveedorRequest,
    CrearProveedorRequest,
    GrupoCompraSugerida,
    ItemCompraSugerida,
    ProveedorDetallePublico,
    ResumenComprasSugeridas,
)
from app.services.lotes_service import evaluar_estado_producto


def _calcular_cantidad_sugerida(
    unidad: str,
    stock_minimo: Decimal,
    stock_vendible: Decimal,
) -> float:
    faltante = float((stock_minimo * Decimal("2")) - stock_vendible)
    if unidad == "KG":
        return max(0.5, round(faltante, 1))
    return float(max(1, math.ceil(faltante)))


def _formatear_cantidad(cantidad: float) -> str:
    if float(cantidad).is_integer():
        return str(int(cantidad))
    return f"{cantidad:.1f}"


def _construir_mensaje_y_url(
    almacen_nombre: str,
    proveedor_nombre: str,
    proveedor_id: int | None,
    telefono_whatsapp: str | None,
    items: list[ItemCompraSugerida],
) -> tuple[str, str]:
    encabezado = (
        f"Hola {proveedor_nombre}, pedido para {almacen_nombre}:"
        if proveedor_id is not None
        else f"Lista de compra presencial - {almacen_nombre}:"
    )
    lineas = [encabezado]
    for item in items:
        lineas.append(f"- {_formatear_cantidad(item.cantidad_sugerida)} {item.unidad} x {item.nombre}")

    mensaje = "\n".join(lineas)
    digitos = "".join(ch for ch in (telefono_whatsapp or "") if ch.isdigit())
    texto_codificado = quote(mensaje)
    url = (
        f"https://wa.me/{digitos}?text={texto_codificado}"
        if digitos
        else f"https://wa.me/?text={texto_codificado}"
    )
    return mensaje, url


def _obtener_proveedor(db: Session, almacen_id: int, proveedor_id: int) -> Proveedor:
    prov = db.scalar(
        select(Proveedor).where(
            Proveedor.id == proveedor_id,
            Proveedor.almacen_id == almacen_id,
        )
    )
    if not prov:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proveedor no encontrado",
        )
    return prov


def _conteo_productos_por_proveedor(db: Session, almacen_id: int) -> dict[int, int]:
    rows = db.execute(
        select(Producto.proveedor_id, func.count(Producto.id))
        .where(
            Producto.almacen_id == almacen_id,
            Producto.activo.is_(True),
            Producto.proveedor_id.is_not(None),
        )
        .group_by(Producto.proveedor_id)
    ).all()
    return {prov_id: int(total) for prov_id, total in rows if prov_id is not None}


def _serializar_proveedor(prov: Proveedor, conteos: dict[int, int]) -> ProveedorDetallePublico:
    return ProveedorDetallePublico(
        id=prov.id,
        nombre=prov.nombre,
        telefono_whatsapp=prov.telefono_whatsapp,
        contacto=prov.contacto,
        activo=prov.activo,
        productos_asociados=conteos.get(prov.id, 0),
    )


def listar_proveedores_detalle(
    db: Session,
    almacen_id: int,
    incluir_inactivos: bool = False,
) -> list[ProveedorDetallePublico]:
    stmt = (
        select(Proveedor)
        .where(Proveedor.almacen_id == almacen_id)
        .order_by(Proveedor.activo.desc(), Proveedor.nombre.asc())
    )
    if not incluir_inactivos:
        stmt = stmt.where(Proveedor.activo.is_(True))

    conteos = _conteo_productos_por_proveedor(db, almacen_id)
    return [_serializar_proveedor(p, conteos) for p in db.scalars(stmt).all()]


def crear_proveedor(
    db: Session,
    usuario: Usuario,
    data: CrearProveedorRequest,
) -> ProveedorDetallePublico:
    existente = db.scalar(
        select(Proveedor).where(
            Proveedor.almacen_id == usuario.almacen_id,
            func.lower(Proveedor.nombre) == data.nombre.lower(),
        )
    )
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un proveedor con ese nombre",
        )

    prov = Proveedor(
        almacen_id=usuario.almacen_id,
        nombre=data.nombre,
        telefono_whatsapp=data.telefono_whatsapp,
        contacto=data.contacto,
        activo=True,
    )
    db.add(prov)
    db.commit()
    db.refresh(prov)
    return _serializar_proveedor(prov, {})


def actualizar_proveedor(
    db: Session,
    usuario: Usuario,
    proveedor_id: int,
    data: ActualizarProveedorRequest,
) -> ProveedorDetallePublico:
    prov = _obtener_proveedor(db, usuario.almacen_id, proveedor_id)
    duplicado = db.scalar(
        select(Proveedor).where(
            Proveedor.almacen_id == usuario.almacen_id,
            func.lower(Proveedor.nombre) == data.nombre.lower(),
            Proveedor.id != prov.id,
        )
    )
    if duplicado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe un proveedor con ese nombre",
        )

    prov.nombre = data.nombre
    prov.telefono_whatsapp = data.telefono_whatsapp
    prov.contacto = data.contacto
    db.commit()
    db.refresh(prov)
    conteos = _conteo_productos_por_proveedor(db, usuario.almacen_id)
    return _serializar_proveedor(prov, conteos)


def cambiar_estado_proveedor(
    db: Session,
    usuario: Usuario,
    proveedor_id: int,
    activo: bool,
) -> ProveedorDetallePublico:
    prov = _obtener_proveedor(db, usuario.almacen_id, proveedor_id)
    prov.activo = activo
    db.commit()
    db.refresh(prov)
    conteos = _conteo_productos_por_proveedor(db, usuario.almacen_id)
    return _serializar_proveedor(prov, conteos)


def obtener_compras_sugeridas(
    db: Session,
    almacen_id: int,
    incluir_todos: bool = False,
) -> ResumenComprasSugeridas:
    almacen = db.get(Almacen, almacen_id)
    almacen_nombre = almacen.nombre if almacen else "StockBarrio"

    productos = (
        db.scalars(
            select(Producto)
            .options(joinedload(Producto.proveedor), joinedload(Producto.lotes))
            .where(Producto.almacen_id == almacen_id, Producto.activo.is_(True))
            .order_by(Producto.nombre.asc())
        )
        .unique()
        .all()
    )

    grupos_map: dict[int | None, dict] = {}
    total_productos = 0
    costo_total = 0

    for prod in productos:
        info = evaluar_estado_producto(prod)
        stock_vendible = Decimal(str(info["stock_vendible"]))
        stock_minimo = Decimal(str(prod.stock_minimo))

        if not incluir_todos and stock_vendible > stock_minimo:
            continue

        cant_sugerida = _calcular_cantidad_sugerida(prod.unidad, stock_minimo, stock_vendible)
        subtotal_est = int(round(cant_sugerida * prod.precio_costo))

        prov_activo = prod.proveedor if (prod.proveedor and prod.proveedor.activo) else None
        clave_prov = prov_activo.id if prov_activo else None

        if clave_prov not in grupos_map:
            grupos_map[clave_prov] = {
                "proveedor": prov_activo,
                "items": [],
                "costo": 0,
            }

        grupos_map[clave_prov]["items"].append(
            ItemCompraSugerida(
                producto_id=prod.id,
                nombre=prod.nombre,
                codigo_barras=prod.codigo_barras,
                unidad=prod.unidad,
                stock_vendible=float(stock_vendible),
                stock_minimo=float(stock_minimo),
                cantidad_sugerida=cant_sugerida,
                precio_costo=prod.precio_costo,
                subtotal_estimado=subtotal_est,
                estado_vencimiento=info["estado_vencimiento"],
            )
        )
        grupos_map[clave_prov]["costo"] += subtotal_est
        total_productos += 1
        costo_total += subtotal_est

    grupos_ordenados = sorted(
        grupos_map.values(),
        key=lambda g: (
            1 if g["proveedor"] is None else 0,
            g["proveedor"].nombre.lower() if g["proveedor"] else "",
        ),
    )

    grupos_publicos: list[GrupoCompraSugerida] = []
    for g in grupos_ordenados:
        prov = g["proveedor"]
        prov_id = prov.id if prov else None
        prov_nombre = prov.nombre if prov else "Compra presencial / Sin proveedor"
        telefono = prov.telefono_whatsapp if prov else None
        contacto = prov.contacto if prov else None
        items = g["items"]

        mensaje, whatsapp_url = _construir_mensaje_y_url(
            almacen_nombre=almacen_nombre,
            proveedor_nombre=prov_nombre,
            proveedor_id=prov_id,
            telefono_whatsapp=telefono,
            items=items,
        )

        grupos_publicos.append(
            GrupoCompraSugerida(
                proveedor_id=prov_id,
                proveedor_nombre=prov_nombre,
                telefono_whatsapp=telefono,
                contacto=contacto,
                total_items=len(items),
                costo_estimado=g["costo"],
                mensaje_whatsapp=mensaje,
                whatsapp_url=whatsapp_url,
                items=items,
            )
        )

    return ResumenComprasSugeridas(
        total_productos_reponer=total_productos,
        total_grupos=len(grupos_publicos),
        costo_total_estimado=costo_total,
        grupos=grupos_publicos,
    )
