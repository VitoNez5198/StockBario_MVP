from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AbonoFiado,
    Cliente,
    DetalleVenta,
    EstadoVenta,
    MetodoPago,
    Usuario,
    Venta,
)
from app.schemas.fiados import (
    AbonoPublico,
    ActualizarClienteRequest,
    ClientePublico,
    CrearClienteRequest,
    MovimientoClientePublico,
    RegistrarAbonoRequest,
    ResumenFiadosPublico,
)
from app.services.pos_service import obtener_caja_abierta


def _serializar_cliente(cliente: Cliente) -> ClientePublico:
    cupo = max(0, cliente.limite_credito - cliente.deuda_actual)
    if cliente.limite_credito > 0:
        porcentaje = min(100.0, round((cliente.deuda_actual / cliente.limite_credito) * 100, 1))
    else:
        porcentaje = 100.0 if cliente.deuda_actual > 0 else 0.0

    return ClientePublico(
        id=cliente.id,
        nombre=cliente.nombre,
        rut_o_apodo=cliente.rut_o_apodo,
        telefono=cliente.telefono,
        direccion=cliente.direccion,
        limite_credito=cliente.limite_credito,
        deuda_actual=cliente.deuda_actual,
        cupo_disponible=cupo,
        porcentaje_uso=porcentaje,
        activo=cliente.activo,
    )


def _obtener_cliente(db: Session, almacen_id: int, cliente_id: int) -> Cliente:
    cliente = db.scalar(
        select(Cliente).where(
            Cliente.id == cliente_id,
            Cliente.almacen_id == almacen_id,
        )
    )
    if not cliente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado",
        )
    return cliente


def obtener_resumen_fiados(db: Session, almacen_id: int) -> ResumenFiadosPublico:
    clientes = db.scalars(
        select(Cliente).where(
            Cliente.almacen_id == almacen_id,
            Cliente.activo.is_(True),
        )
    ).all()

    return ResumenFiadosPublico(
        total_clientes_activos=len(clientes),
        clientes_con_deuda=sum(1 for c in clientes if c.deuda_actual > 0),
        deuda_total=sum(c.deuda_actual for c in clientes),
        cupo_total=sum(c.limite_credito for c in clientes),
    )


def listar_clientes(
    db: Session,
    almacen_id: int,
    q: str | None = None,
    solo_con_deuda: bool = False,
    incluir_inactivos: bool = False,
) -> list[ClientePublico]:
    stmt = (
        select(Cliente)
        .where(Cliente.almacen_id == almacen_id)
        .order_by(Cliente.activo.desc(), Cliente.deuda_actual.desc(), Cliente.nombre.asc())
    )
    if not incluir_inactivos:
        stmt = stmt.where(Cliente.activo.is_(True))
    if solo_con_deuda:
        stmt = stmt.where(Cliente.deuda_actual > 0)
    if q and q.strip():
        termino = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Cliente.nombre.ilike(termino),
                Cliente.rut_o_apodo.ilike(termino),
                Cliente.telefono.ilike(termino),
            )
        )

    return [_serializar_cliente(c) for c in db.scalars(stmt).all()]


def crear_cliente(
    db: Session,
    usuario: Usuario,
    data: CrearClienteRequest,
) -> ClientePublico:
    cliente = Cliente(
        almacen_id=usuario.almacen_id,
        nombre=data.nombre,
        rut_o_apodo=data.rut_o_apodo,
        telefono=data.telefono,
        direccion=data.direccion,
        limite_credito=data.limite_credito,
        deuda_actual=0,
        activo=True,
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return _serializar_cliente(cliente)


def actualizar_cliente(
    db: Session,
    usuario: Usuario,
    cliente_id: int,
    data: ActualizarClienteRequest,
) -> ClientePublico:
    cliente = _obtener_cliente(db, usuario.almacen_id, cliente_id)
    cliente.nombre = data.nombre
    cliente.rut_o_apodo = data.rut_o_apodo
    cliente.telefono = data.telefono
    cliente.direccion = data.direccion
    cliente.limite_credito = data.limite_credito
    db.commit()
    db.refresh(cliente)
    return _serializar_cliente(cliente)


def cambiar_estado_cliente(
    db: Session,
    usuario: Usuario,
    cliente_id: int,
    activo: bool,
) -> ClientePublico:
    cliente = _obtener_cliente(db, usuario.almacen_id, cliente_id)
    if not activo and cliente.deuda_actual > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar un cliente con deuda pendiente",
        )
    cliente.activo = activo
    db.commit()
    db.refresh(cliente)
    return _serializar_cliente(cliente)


def registrar_abono(
    db: Session,
    usuario: Usuario,
    cliente_id: int,
    data: RegistrarAbonoRequest,
) -> AbonoPublico:
    caja = obtener_caja_abierta(db, usuario.almacen_id)
    if caja is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes abrir caja antes de registrar abonos",
        )

    cliente = _obtener_cliente(db, usuario.almacen_id, cliente_id)
    if not cliente.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cliente esta inactivo",
        )
    if cliente.deuda_actual <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cliente no registra deuda pendiente",
        )
    if data.monto > cliente.deuda_actual:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El abono supera la deuda actual",
        )

    cliente.deuda_actual -= data.monto
    abono = AbonoFiado(
        cliente_id=cliente.id,
        sesion_caja_id=caja.id,
        usuario_id=usuario.id,
        monto=data.monto,
        metodo_pago=data.metodo_pago,
        observacion=data.observacion,
    )
    db.add(abono)
    db.commit()
    db.refresh(abono)

    return AbonoPublico(
        id=abono.id,
        cliente_id=cliente.id,
        sesion_caja_id=abono.sesion_caja_id,
        usuario_id=usuario.id,
        usuario_nombre=usuario.nombre,
        monto=abono.monto,
        metodo_pago=abono.metodo_pago,
        observacion=abono.observacion,
        creado_en=abono.creado_en,
        deuda_restante=cliente.deuda_actual,
    )


def listar_movimientos_cliente(
    db: Session,
    almacen_id: int,
    cliente_id: int,
    limit: int = 50,
) -> list[MovimientoClientePublico]:
    _obtener_cliente(db, almacen_id, cliente_id)

    ventas_fiado = (
        db.scalars(
            select(Venta)
            .options(
                joinedload(Venta.usuario),
                joinedload(Venta.items).joinedload(DetalleVenta.producto),
            )
            .where(
                Venta.almacen_id == almacen_id,
                Venta.cliente_id == cliente_id,
                Venta.metodo_pago == MetodoPago.FIADO.value,
            )
            .order_by(Venta.creada_en.desc())
            .limit(limit)
        )
        .unique()
        .all()
    )

    abonos_rows = db.execute(
        select(AbonoFiado, Usuario.nombre)
        .join(Usuario, AbonoFiado.usuario_id == Usuario.id)
        .where(AbonoFiado.cliente_id == cliente_id)
        .order_by(AbonoFiado.creado_en.desc())
        .limit(limit)
    ).all()

    movimientos: list[MovimientoClientePublico] = []
    for v in ventas_fiado:
        resumen_items = ", ".join(
            f"{float(i.cantidad):g}x {i.producto.nombre}" for i in v.items if i.producto
        )
        es_anulada = v.estado == EstadoVenta.ANULADA.value
        movimientos.append(
            MovimientoClientePublico(
                tipo="ANULACION_FIADO" if es_anulada else "FIADO",
                fecha=v.creada_en,
                monto=v.total,
                referencia=v.folio,
                detalle=(
                    f"Venta anulada ({resumen_items})"
                    if es_anulada
                    else (resumen_items or "Compra fiada")
                ),
                usuario_nombre=v.usuario.nombre if v.usuario else "",
            )
        )

    for abono, user_nombre in abonos_rows:
        movimientos.append(
            MovimientoClientePublico(
                tipo="ABONO",
                fecha=abono.creado_en,
                monto=abono.monto,
                referencia=abono.metodo_pago,
                detalle=abono.observacion or f"Abono en {abono.metodo_pago.lower()}",
                usuario_nombre=user_nombre,
            )
        )

    movimientos.sort(key=lambda m: m.fecha, reverse=True)
    return movimientos[:limit]
