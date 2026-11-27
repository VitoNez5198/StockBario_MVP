from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models import LoteProducto, Producto


def clasificar_vencimiento(fecha_vencimiento: date | None) -> tuple[str, bool]:
    if fecha_vencimiento is None:
        return "SIN_FECHA", False
    hoy = date.today()
    if fecha_vencimiento < hoy:
        return "VENCIDO", True
    if fecha_vencimiento.toordinal() - hoy.toordinal() <= 7:
        return "POR_VENCER", False
    return "OPTIMO", False


def _clave_orden_lote(lote: LoteProducto) -> tuple[int, date, int]:
    sin_fecha = 1 if lote.fecha_vencimiento is None else 0
    return (sin_fecha, lote.fecha_vencimiento or date.max, lote.id or 0)


def obtener_lotes_activos(db: Session, producto_id: int) -> list[LoteProducto]:
    stmt = (
        select(LoteProducto)
        .where(
            LoteProducto.producto_id == producto_id,
            LoteProducto.cantidad_disponible > 0,
        )
        .order_by(
            case((LoteProducto.fecha_vencimiento.is_(None), 1), else_=0),
            LoteProducto.fecha_vencimiento.asc(),
            LoteProducto.id.asc(),
        )
    )
    return list(db.scalars(stmt).all())


def evaluar_estado_producto(
    producto: Producto,
    lotes_activos: list[LoteProducto] | None = None,
) -> dict:
    if lotes_activos is None:
        lotes_activos = [
            l for l in (producto.lotes or []) if Decimal(str(l.cantidad_disponible)) > 0
        ]
        lotes_activos.sort(key=_clave_orden_lote)

    if not lotes_activos:
        estado, bloqueado = clasificar_vencimiento(producto.fecha_vencimiento)
        stock_total = Decimal(str(producto.stock_actual))
        return {
            "estado_vencimiento": estado,
            "bloqueado_venta": bloqueado,
            "proxima_fecha": producto.fecha_vencimiento,
            "stock_vendible": Decimal("0") if bloqueado else stock_total,
            "stock_vencido": stock_total if bloqueado else Decimal("0"),
            "lotes_activos": [],
        }

    hoy = date.today()
    stock_vencido = Decimal("0")
    stock_vendible = Decimal("0")
    fechas_vigentes: list[date] = []
    fechas_vencidas: list[date] = []

    for lote in lotes_activos:
        cant = Decimal(str(lote.cantidad_disponible))
        if lote.fecha_vencimiento is not None and lote.fecha_vencimiento < hoy:
            stock_vencido += cant
            fechas_vencidas.append(lote.fecha_vencimiento)
        else:
            stock_vendible += cant
            if lote.fecha_vencimiento is not None:
                fechas_vigentes.append(lote.fecha_vencimiento)

    if stock_vendible > 0:
        proxima = min(fechas_vigentes) if fechas_vigentes else None
        estado, _ = clasificar_vencimiento(proxima)
        return {
            "estado_vencimiento": estado,
            "bloqueado_venta": False,
            "proxima_fecha": proxima,
            "stock_vendible": stock_vendible,
            "stock_vencido": stock_vencido,
            "lotes_activos": lotes_activos,
        }

    proxima_vencida = min(fechas_vencidas) if fechas_vencidas else None
    return {
        "estado_vencimiento": "VENCIDO",
        "bloqueado_venta": True,
        "proxima_fecha": proxima_vencida,
        "stock_vendible": Decimal("0"),
        "stock_vencido": stock_vencido,
        "lotes_activos": lotes_activos,
    }


def sincronizar_producto_desde_lotes(db: Session, producto: Producto) -> None:
    db.flush()
    tiene_lotes = db.scalar(
        select(LoteProducto.id).where(LoteProducto.producto_id == producto.id).limit(1)
    )
    if tiene_lotes is None:
        return

    activos = obtener_lotes_activos(db, producto.id)
    if not activos:
        producto.stock_actual = Decimal("0")
        db.expire(producto, ["lotes"])
        return

    hoy = date.today()
    stock_total = sum(Decimal(str(l.cantidad_disponible)) for l in activos)
    fechas_vigentes = [
        l.fecha_vencimiento
        for l in activos
        if l.fecha_vencimiento is not None and l.fecha_vencimiento >= hoy
    ]
    fechas_vencidas = [
        l.fecha_vencimiento
        for l in activos
        if l.fecha_vencimiento is not None and l.fecha_vencimiento < hoy
    ]

    producto.stock_actual = stock_total
    if fechas_vigentes:
        producto.fecha_vencimiento = min(fechas_vigentes)
    elif fechas_vencidas:
        producto.fecha_vencimiento = min(fechas_vencidas)
    else:
        producto.fecha_vencimiento = None
    db.expire(producto, ["lotes"])


def agregar_stock_lote(
    db: Session,
    producto: Producto,
    cantidad: Decimal,
    fecha_vencimiento: date | None,
) -> None:
    tiene_lotes = db.scalar(
        select(LoteProducto.id).where(LoteProducto.producto_id == producto.id).limit(1)
    )
    stock_actual = Decimal(str(producto.stock_actual))

    if tiene_lotes is None and stock_actual > 0:
        db.add(
            LoteProducto(
                producto_id=producto.id,
                cantidad_disponible=stock_actual,
                fecha_vencimiento=producto.fecha_vencimiento,
            )
        )
        db.flush()

    lote_misma_fecha = db.scalar(
        select(LoteProducto)
        .where(
            LoteProducto.producto_id == producto.id,
            LoteProducto.fecha_vencimiento == fecha_vencimiento,
            LoteProducto.cantidad_disponible > 0,
        )
        .order_by(LoteProducto.id.asc())
        .limit(1)
    )
    if lote_misma_fecha is not None:
        lote_misma_fecha.cantidad_disponible = (
            Decimal(str(lote_misma_fecha.cantidad_disponible)) + cantidad
        )
    else:
        db.add(
            LoteProducto(
                producto_id=producto.id,
                cantidad_disponible=cantidad,
                fecha_vencimiento=fecha_vencimiento,
            )
        )

    sincronizar_producto_desde_lotes(db, producto)


def descontar_fefo(
    db: Session,
    producto: Producto,
    cantidad: Decimal,
    solo_vigentes: bool = True,
    lote_id: int | None = None,
) -> None:
    if lote_id is not None:
        lote = db.scalar(
            select(LoteProducto).where(
                LoteProducto.id == lote_id,
                LoteProducto.producto_id == producto.id,
            )
        )
        if lote is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tanda o lote no encontrado",
            )
        disponible = Decimal(str(lote.cantidad_disponible))
        if disponible < cantidad:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad supera el stock disponible de la tanda",
            )
        lote.cantidad_disponible = disponible - cantidad
        sincronizar_producto_desde_lotes(db, producto)
        return

    activos = obtener_lotes_activos(db, producto.id)
    if not activos:
        stock_ant = Decimal(str(producto.stock_actual))
        if stock_ant < cantidad:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente para {producto.nombre}",
            )
        producto.stock_actual = stock_ant - cantidad
        return

    hoy = date.today()
    elegibles = (
        [l for l in activos if l.fecha_vencimiento is None or l.fecha_vencimiento >= hoy]
        if solo_vigentes
        else activos
    )
    disponible_total = sum(Decimal(str(l.cantidad_disponible)) for l in elegibles)
    if disponible_total < cantidad:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Stock vigente insuficiente para {producto.nombre}"
                if solo_vigentes
                else f"Stock insuficiente para {producto.nombre}"
            ),
        )

    restante = cantidad
    for lote in elegibles:
        if restante <= 0:
            break
        disp = Decimal(str(lote.cantidad_disponible))
        tomar = min(disp, restante)
        lote.cantidad_disponible = disp - tomar
        restante -= tomar

    sincronizar_producto_desde_lotes(db, producto)


def restaurar_stock_anulacion(
    db: Session,
    producto: Producto,
    cantidad: Decimal,
) -> None:
    tiene_lotes = db.scalar(
        select(LoteProducto.id).where(LoteProducto.producto_id == producto.id).limit(1)
    )
    if tiene_lotes is None:
        producto.stock_actual = Decimal(str(producto.stock_actual)) + cantidad
        return

    hoy = date.today()
    lote_vigente = db.scalar(
        select(LoteProducto)
        .where(
            LoteProducto.producto_id == producto.id,
            (LoteProducto.fecha_vencimiento.is_(None)) | (LoteProducto.fecha_vencimiento >= hoy),
        )
        .order_by(
            case((LoteProducto.fecha_vencimiento.is_(None), 1), else_=0),
            LoteProducto.fecha_vencimiento.desc(),
            LoteProducto.id.desc(),
        )
        .limit(1)
    )
    if lote_vigente is not None:
        lote_vigente.cantidad_disponible = Decimal(str(lote_vigente.cantidad_disponible)) + cantidad
    else:
        db.add(
            LoteProducto(
                producto_id=producto.id,
                cantidad_disponible=cantidad,
                fecha_vencimiento=producto.fecha_vencimiento,
            )
        )
    sincronizar_producto_desde_lotes(db, producto)
