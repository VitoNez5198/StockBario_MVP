from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Cliente,
    DetalleVenta,
    EstadoCaja,
    EstadoVenta,
    MetodoPago,
    MovimientoStock,
    Producto,
    SesionCaja,
    TipoMovimiento,
    Usuario,
    Venta,
)
from app.schemas.pos import (
    CrearVentaRequest,
    DetalleVentaPublico,
    ProductoPosPublico,
    VentaPublica,
)


def clasificar_vencimiento(fecha_vencimiento: date | None) -> tuple[str, bool]:
    if fecha_vencimiento is None:
        return "SIN_FECHA", False
    hoy = date.today()
    if fecha_vencimiento < hoy:
        return "VENCIDO", True
    if fecha_vencimiento <= hoy + timedelta(days=7):
        return "POR_VENCER", False
    return "OPTIMO", False


def obtener_caja_abierta(db: Session, almacen_id: int) -> SesionCaja | None:
    return db.scalar(
        select(SesionCaja)
        .where(
            SesionCaja.almacen_id == almacen_id,
            SesionCaja.estado == EstadoCaja.ABIERTA.value,
        )
        .order_by(SesionCaja.id.desc())
        .limit(1)
    )


def abrir_caja(db: Session, usuario: Usuario, fondo_inicial: int) -> SesionCaja:
    if obtener_caja_abierta(db, usuario.almacen_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una caja abierta",
        )
    sesion = SesionCaja(
        almacen_id=usuario.almacen_id,
        usuario_apertura_id=usuario.id,
        fondo_inicial=fondo_inicial,
        estado=EstadoCaja.ABIERTA.value,
    )
    db.add(sesion)
    db.commit()
    db.refresh(sesion)
    return sesion


def listar_productos_pos(
    db: Session,
    almacen_id: int,
    q: str | None = None,
) -> list[ProductoPosPublico]:
    stmt = (
        select(Producto)
        .options(joinedload(Producto.categoria))
        .where(
            Producto.almacen_id == almacen_id,
            Producto.activo.is_(True),
        )
    )
    if q and q.strip():
        termino = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Producto.nombre.ilike(termino),
                Producto.codigo_barras.ilike(termino),
            )
        )
    productos = db.scalars(stmt.order_by(Producto.nombre.asc())).all()

    resultado = []
    for p in productos:
        estado_v, bloqueado = clasificar_vencimiento(p.fecha_vencimiento)
        resultado.append(
            ProductoPosPublico(
                id=p.id,
                codigo_barras=p.codigo_barras,
                nombre=p.nombre,
                categoria_nombre=p.categoria.nombre if p.categoria else "General",
                unidad=p.unidad,
                precio_venta=p.precio_venta,
                stock_actual=float(p.stock_actual),
                stock_minimo=float(p.stock_minimo),
                fecha_vencimiento=p.fecha_vencimiento,
                estado_vencimiento=estado_v,
                bloqueado_venta=bloqueado,
            )
        )
    return resultado


def _generar_folio(db: Session, almacen_id: int) -> str:
    ahora = datetime.now(timezone.utc)
    prefijo = f"SB-{ahora.strftime('%Y%m%d')}-"
    existentes = db.scalar(
        select(func.count(Venta.id)).where(
            Venta.almacen_id == almacen_id,
            Venta.folio.like(f"{prefijo}%"),
        )
    )
    correlativo = int(existentes or 0) + 1
    return f"{prefijo}{correlativo:04d}"


def serializar_venta(venta: Venta) -> VentaPublica:
    return VentaPublica(
        id=venta.id,
        folio=venta.folio,
        sesion_caja_id=venta.sesion_caja_id,
        usuario_id=venta.usuario_id,
        usuario_nombre=venta.usuario.nombre if venta.usuario else "",
        cliente_id=venta.cliente_id,
        metodo_pago=venta.metodo_pago,
        total=venta.total,
        monto_recibido=venta.monto_recibido,
        vuelto=venta.vuelto,
        estado=venta.estado,
        creada_en=venta.creada_en,
        items=[
            DetalleVentaPublico(
                id=item.id,
                producto_id=item.producto_id,
                producto_nombre=item.producto.nombre if item.producto else "",
                cantidad=float(item.cantidad),
                precio_venta_momento=item.precio_venta_momento,
                subtotal=item.subtotal,
            )
            for item in venta.items
        ],
    )


def registrar_venta(db: Session, usuario: Usuario, data: CrearVentaRequest) -> Venta:
    caja = obtener_caja_abierta(db, usuario.almacen_id)
    if caja is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes abrir caja antes de registrar ventas",
        )

    # Agrupar cantidades si el mismo producto viene repetido en el carrito
    cantidades_por_id: dict[int, Decimal] = {}
    for item in data.items:
        cantidades_por_id[item.producto_id] = (
            cantidades_por_id.get(item.producto_id, Decimal("0")) + Decimal(str(item.cantidad))
        )

    productos = db.scalars(
        select(Producto).where(
            Producto.id.in_(list(cantidades_por_id.keys())),
            Producto.almacen_id == usuario.almacen_id,
            Producto.activo.is_(True),
        )
    ).all()
    mapa_productos = {p.id: p for p in productos}

    detalles_a_crear: list[tuple[Producto, Decimal, int]] = []
    total_venta = 0

    for prod_id, cantidad in cantidades_por_id.items():
        producto = mapa_productos.get(prod_id)
        if producto is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Producto no encontrado",
            )

        _, bloqueado = clasificar_vencimiento(producto.fecha_vencimiento)
        if bloqueado:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Producto vencido: {producto.nombre}",
            )

        stock_actual = Decimal(str(producto.stock_actual))
        if stock_actual < cantidad:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente para {producto.nombre}",
            )

        subtotal = int(round(cantidad * Decimal(producto.precio_venta)))
        total_venta += subtotal
        detalles_a_crear.append((producto, cantidad, subtotal))

    vuelto = 0
    monto_recibido = data.monto_recibido
    cliente_id = None

    if data.metodo_pago == MetodoPago.EFECTIVO:
        if monto_recibido is None or monto_recibido < total_venta:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Monto recibido insuficiente",
            )
        vuelto = monto_recibido - total_venta
    elif data.metodo_pago == MetodoPago.FIADO:
        if not data.cliente_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debes seleccionar un cliente para venta fiada",
            )
        cliente = db.scalar(
            select(Cliente).where(
                Cliente.id == data.cliente_id,
                Cliente.almacen_id == usuario.almacen_id,
                Cliente.activo.is_(True),
            )
        )
        if cliente is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cliente no encontrado",
            )
        if cliente.deuda_actual + total_venta > cliente.limite_credito:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Supera el limite de credito del cliente",
            )
        cliente.deuda_actual += total_venta
        cliente_id = cliente.id

    venta = Venta(
        almacen_id=usuario.almacen_id,
        sesion_caja_id=caja.id,
        usuario_id=usuario.id,
        cliente_id=cliente_id,
        folio=_generar_folio(db, usuario.almacen_id),
        metodo_pago=data.metodo_pago.value,
        total=total_venta,
        monto_recibido=monto_recibido,
        vuelto=vuelto,
        estado=EstadoVenta.COMPLETADA.value,
    )
    db.add(venta)
    db.flush()

    for producto, cantidad, subtotal in detalles_a_crear:
        stock_ant = Decimal(str(producto.stock_actual))
        stock_nvo = stock_ant - cantidad
        producto.stock_actual = stock_nvo

        db.add(
            DetalleVenta(
                venta_id=venta.id,
                producto_id=producto.id,
                cantidad=cantidad,
                precio_costo_momento=producto.precio_costo,
                precio_venta_momento=producto.precio_venta,
                subtotal=subtotal,
            )
        )
        db.add(
            MovimientoStock(
                producto_id=producto.id,
                usuario_id=usuario.id,
                tipo=TipoMovimiento.VENTA.value,
                cantidad=cantidad,
                stock_anterior=stock_ant,
                stock_nuevo=stock_nvo,
                motivo=f"Venta {venta.folio}",
            )
        )

    db.commit()
    return obtener_venta_con_detalle(db, usuario.almacen_id, venta.id)


def obtener_venta_con_detalle(db: Session, almacen_id: int, venta_id: int) -> Venta:
    venta = db.scalar(
        select(Venta)
        .options(
            joinedload(Venta.usuario),
            joinedload(Venta.items).joinedload(DetalleVenta.producto),
        )
        .where(Venta.id == venta_id, Venta.almacen_id == almacen_id)
    )
    if venta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venta no encontrada",
        )
    return venta


def listar_ventas(
    db: Session,
    almacen_id: int,
    solo_turno: bool = True,
) -> list[Venta]:
    stmt = (
        select(Venta)
        .options(
            joinedload(Venta.usuario),
            joinedload(Venta.items).joinedload(DetalleVenta.producto),
        )
        .where(Venta.almacen_id == almacen_id)
    )
    if solo_turno:
        caja = obtener_caja_abierta(db, almacen_id)
        if caja is None:
            return []
        stmt = stmt.where(Venta.sesion_caja_id == caja.id)

    ventas = db.scalars(stmt.order_by(Venta.id.desc())).unique().all()
    return list(ventas)


def anular_venta(db: Session, usuario: Usuario, venta_id: int) -> Venta:
    venta = obtener_venta_con_detalle(db, usuario.almacen_id, venta_id)
    if venta.estado == EstadoVenta.ANULADA.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La venta ya esta anulada",
        )

    venta.estado = EstadoVenta.ANULADA.value

    for item in venta.items:
        producto = db.get(Producto, item.producto_id)
        if producto is not None:
            stock_ant = Decimal(str(producto.stock_actual))
            cant = Decimal(str(item.cantidad))
            stock_nvo = stock_ant + cant
            producto.stock_actual = stock_nvo
            db.add(
                MovimientoStock(
                    producto_id=producto.id,
                    usuario_id=usuario.id,
                    tipo=TipoMovimiento.ANULACION.value,
                    cantidad=cant,
                    stock_anterior=stock_ant,
                    stock_nuevo=stock_nvo,
                    motivo=f"Anulacion {venta.folio}",
                )
            )

    if venta.metodo_pago == MetodoPago.FIADO.value and venta.cliente_id:
        cliente = db.get(Cliente, venta.cliente_id)
        if cliente is not None:
            cliente.deuda_actual = max(0, cliente.deuda_actual - venta.total)

    db.commit()
    return obtener_venta_con_detalle(db, usuario.almacen_id, venta.id)
