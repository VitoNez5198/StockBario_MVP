from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Categoria,
    LoteProducto,
    MovimientoStock,
    Producto,
    Proveedor,
    RolUsuario,
    TipoMovimiento,
    Usuario,
)
from app.schemas.inventario import (
    ActualizarProductoRequest,
    CrearCategoriaRequest,
    CrearProductoRequest,
    LoteProductoPublico,
    MovimientoStockPublico,
    ProductoInventarioPublico,
    RegistrarMovimientoRequest,
    ResumenInventarioPublico,
)
from app.services.lotes_service import (
    agregar_stock_lote,
    clasificar_vencimiento,
    descontar_fefo,
    evaluar_estado_producto,
    obtener_lotes_activos,
    sincronizar_producto_desde_lotes,
)


def _serializar_producto(producto: Producto) -> ProductoInventarioPublico:
    info = evaluar_estado_producto(producto)
    lotes_pub = []
    for lote in info["lotes_activos"]:
        estado_l, vencido = clasificar_vencimiento(lote.fecha_vencimiento)
        lotes_pub.append(
            LoteProductoPublico(
                id=lote.id,
                cantidad_disponible=float(lote.cantidad_disponible),
                fecha_vencimiento=lote.fecha_vencimiento,
                estado_vencimiento=estado_l,
                vencido=vencido,
            )
        )

    return ProductoInventarioPublico(
        id=producto.id,
        codigo_barras=producto.codigo_barras,
        nombre=producto.nombre,
        categoria_id=producto.categoria_id,
        categoria_nombre=producto.categoria.nombre if producto.categoria else None,
        proveedor_id=producto.proveedor_id,
        proveedor_nombre=producto.proveedor.nombre if producto.proveedor else None,
        unidad=producto.unidad,
        precio_costo=producto.precio_costo,
        precio_venta=producto.precio_venta,
        stock_actual=float(producto.stock_actual),
        stock_vendible=float(info["stock_vendible"]),
        stock_vencido=float(info["stock_vencido"]),
        stock_minimo=float(producto.stock_minimo),
        stock_bajo=producto.stock_actual <= producto.stock_minimo,
        fecha_vencimiento=info["proxima_fecha"],
        estado_vencimiento=info["estado_vencimiento"],
        bloqueado_venta=info["bloqueado_venta"],
        activo=producto.activo,
        lotes=lotes_pub,
    )


def _obtener_producto(db: Session, almacen_id: int, producto_id: int) -> Producto:
    producto = (
        db.scalars(
            select(Producto)
            .options(
                joinedload(Producto.categoria),
                joinedload(Producto.proveedor),
                joinedload(Producto.lotes),
            )
            .where(Producto.id == producto_id, Producto.almacen_id == almacen_id)
        )
        .unique()
        .first()
    )
    if not producto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado",
        )
    return producto


def _validar_relaciones_y_codigo(
    db: Session,
    almacen_id: int,
    codigo_barras: str | None,
    categoria_id: int | None,
    proveedor_id: int | None,
    excluir_producto_id: int | None = None,
) -> None:
    if codigo_barras:
        stmt = select(Producto).where(
            Producto.almacen_id == almacen_id,
            Producto.codigo_barras == codigo_barras,
        )
        if excluir_producto_id is not None:
            stmt = stmt.where(Producto.id != excluir_producto_id)
        if db.scalar(stmt) is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya existe un producto con ese codigo de barras",
            )

    if categoria_id is not None:
        cat = db.scalar(
            select(Categoria).where(
                Categoria.id == categoria_id,
                Categoria.almacen_id == almacen_id,
            )
        )
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria no encontrada",
            )

    if proveedor_id is not None:
        prov = db.scalar(
            select(Proveedor).where(
                Proveedor.id == proveedor_id,
                Proveedor.almacen_id == almacen_id,
                Proveedor.activo.is_(True),
            )
        )
        if not prov:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proveedor no encontrado",
            )


def listar_categorias(db: Session, almacen_id: int) -> list[Categoria]:
    return list(
        db.scalars(
            select(Categoria)
            .where(Categoria.almacen_id == almacen_id)
            .order_by(Categoria.nombre.asc())
        ).all()
    )


def crear_categoria(
    db: Session,
    usuario: Usuario,
    data: CrearCategoriaRequest,
) -> Categoria:
    existente = db.scalar(
        select(Categoria).where(
            Categoria.almacen_id == usuario.almacen_id,
            func.lower(Categoria.nombre) == data.nombre.lower(),
        )
    )
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una categoria con ese nombre",
        )
    categoria = Categoria(almacen_id=usuario.almacen_id, nombre=data.nombre)
    db.add(categoria)
    db.commit()
    db.refresh(categoria)
    return categoria


def listar_proveedores(db: Session, almacen_id: int) -> list[Proveedor]:
    return list(
        db.scalars(
            select(Proveedor)
            .where(Proveedor.almacen_id == almacen_id, Proveedor.activo.is_(True))
            .order_by(Proveedor.nombre.asc())
        ).all()
    )


def listar_productos(
    db: Session,
    almacen_id: int,
    q: str | None = None,
    categoria_id: int | None = None,
    estado_vencimiento: str | None = None,
    solo_stock_bajo: bool = False,
    incluir_inactivos: bool = False,
) -> list[ProductoInventarioPublico]:
    stmt = (
        select(Producto)
        .options(
            joinedload(Producto.categoria),
            joinedload(Producto.proveedor),
            joinedload(Producto.lotes),
        )
        .where(Producto.almacen_id == almacen_id)
        .order_by(Producto.activo.desc(), Producto.nombre.asc())
    )
    if not incluir_inactivos:
        stmt = stmt.where(Producto.activo.is_(True))
    if categoria_id is not None:
        stmt = stmt.where(Producto.categoria_id == categoria_id)
    if q and q.strip():
        termino = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Producto.nombre.ilike(termino),
                Producto.codigo_barras.ilike(termino),
            )
        )

    items = [_serializar_producto(p) for p in db.scalars(stmt).unique().all()]
    if estado_vencimiento:
        items = [p for p in items if p.estado_vencimiento == estado_vencimiento]
    if solo_stock_bajo:
        items = [p for p in items if p.stock_bajo]
    return items


def obtener_resumen_inventario(db: Session, almacen_id: int) -> ResumenInventarioPublico:
    productos = (
        db.scalars(
            select(Producto)
            .options(joinedload(Producto.lotes))
            .where(Producto.almacen_id == almacen_id)
        )
        .unique()
        .all()
    )

    total_activos = 0
    total_inactivos = 0
    stock_bajo = 0
    por_vencer = 0
    vencidos = 0

    for prod in productos:
        if not prod.activo:
            total_inactivos += 1
            continue
        total_activos += 1
        if prod.stock_actual <= prod.stock_minimo:
            stock_bajo += 1
        info = evaluar_estado_producto(prod)
        if info["estado_vencimiento"] == "POR_VENCER":
            por_vencer += 1
        if info["estado_vencimiento"] == "VENCIDO" or info["stock_vencido"] > 0:
            vencidos += 1

    return ResumenInventarioPublico(
        total_activos=total_activos,
        total_inactivos=total_inactivos,
        stock_bajo=stock_bajo,
        por_vencer=por_vencer,
        vencidos=vencidos,
    )


def crear_producto(
    db: Session,
    usuario: Usuario,
    data: CrearProductoRequest,
) -> ProductoInventarioPublico:
    _validar_relaciones_y_codigo(
        db,
        usuario.almacen_id,
        data.codigo_barras,
        data.categoria_id,
        data.proveedor_id,
    )
    producto = Producto(
        almacen_id=usuario.almacen_id,
        categoria_id=data.categoria_id,
        proveedor_id=data.proveedor_id,
        codigo_barras=data.codigo_barras,
        nombre=data.nombre,
        unidad=data.unidad,
        precio_costo=data.precio_costo,
        precio_venta=data.precio_venta,
        stock_actual=data.stock_actual,
        stock_minimo=data.stock_minimo,
        fecha_vencimiento=data.fecha_vencimiento,
        activo=True,
    )
    db.add(producto)
    db.flush()

    if data.stock_actual > Decimal("0"):
        if data.fecha_vencimiento is not None:
            db.add(
                LoteProducto(
                    producto_id=producto.id,
                    cantidad_disponible=data.stock_actual,
                    fecha_vencimiento=data.fecha_vencimiento,
                )
            )
        db.add(
            MovimientoStock(
                producto_id=producto.id,
                usuario_id=usuario.id,
                tipo=TipoMovimiento.ENTRADA.value,
                cantidad=data.stock_actual,
                stock_anterior=Decimal("0"),
                stock_nuevo=data.stock_actual,
                motivo="Stock inicial",
            )
        )

    db.commit()
    return _serializar_producto(_obtener_producto(db, usuario.almacen_id, producto.id))


def actualizar_producto(
    db: Session,
    usuario: Usuario,
    producto_id: int,
    data: ActualizarProductoRequest,
) -> ProductoInventarioPublico:
    producto = _obtener_producto(db, usuario.almacen_id, producto_id)
    _validar_relaciones_y_codigo(
        db,
        usuario.almacen_id,
        data.codigo_barras,
        data.categoria_id,
        data.proveedor_id,
        excluir_producto_id=producto.id,
    )

    producto.nombre = data.nombre
    producto.codigo_barras = data.codigo_barras
    producto.categoria_id = data.categoria_id
    producto.proveedor_id = data.proveedor_id
    producto.unidad = data.unidad
    producto.precio_costo = data.precio_costo
    producto.precio_venta = data.precio_venta
    producto.stock_minimo = data.stock_minimo

    activos = obtener_lotes_activos(db, producto.id)
    if len(activos) == 0:
        producto.fecha_vencimiento = data.fecha_vencimiento
    elif len(activos) == 1:
        activos[0].fecha_vencimiento = data.fecha_vencimiento
        sincronizar_producto_desde_lotes(db, producto)
    else:
        sincronizar_producto_desde_lotes(db, producto)

    db.commit()
    return _serializar_producto(_obtener_producto(db, usuario.almacen_id, producto.id))


def cambiar_estado_producto(
    db: Session,
    usuario: Usuario,
    producto_id: int,
    activo: bool,
) -> ProductoInventarioPublico:
    producto = _obtener_producto(db, usuario.almacen_id, producto_id)
    producto.activo = activo
    db.commit()
    return _serializar_producto(_obtener_producto(db, usuario.almacen_id, producto.id))


def registrar_movimiento_stock(
    db: Session,
    usuario: Usuario,
    producto_id: int,
    data: RegistrarMovimientoRequest,
) -> MovimientoStockPublico:
    if data.tipo in ("ENTRADA", "AJUSTE") and usuario.rol != RolUsuario.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden registrar entradas o ajustes",
        )

    producto = _obtener_producto(db, usuario.almacen_id, producto_id)
    stock_anterior = Decimal(str(producto.stock_actual))
    activos = obtener_lotes_activos(db, producto.id)

    if data.tipo == TipoMovimiento.ENTRADA.value:
        if data.cantidad <= Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad de entrada debe ser mayor a cero",
            )
        delta = data.cantidad
        if data.fecha_vencimiento is not None or activos:
            agregar_stock_lote(db, producto, data.cantidad, data.fecha_vencimiento)
        else:
            producto.stock_actual = stock_anterior + data.cantidad
    elif data.tipo == TipoMovimiento.MERMA.value:
        if data.cantidad <= Decimal("0"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cantidad de merma debe ser mayor a cero",
            )
        if data.lote_id is not None or activos:
            descontar_fefo(
                db,
                producto,
                data.cantidad,
                solo_vigentes=False,
                lote_id=data.lote_id,
            )
        else:
            stock_calc = stock_anterior - data.cantidad
            if stock_calc < Decimal("0"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La merma supera el stock actual",
                )
            producto.stock_actual = stock_calc
        delta = -data.cantidad
    else:
        if data.cantidad == stock_anterior:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El stock ajustado es igual al stock actual",
            )
        if activos:
            if data.cantidad < stock_anterior:
                descontar_fefo(
                    db,
                    producto,
                    stock_anterior - data.cantidad,
                    solo_vigentes=False,
                )
            else:
                fecha_dest = (
                    data.fecha_vencimiento
                    if data.fecha_vencimiento is not None
                    else producto.fecha_vencimiento
                )
                agregar_stock_lote(db, producto, data.cantidad - stock_anterior, fecha_dest)
        else:
            producto.stock_actual = data.cantidad
        delta = Decimal(str(producto.stock_actual)) - stock_anterior

    stock_nuevo = Decimal(str(producto.stock_actual))
    movimiento = MovimientoStock(
        producto_id=producto.id,
        usuario_id=usuario.id,
        tipo=data.tipo,
        cantidad=delta,
        stock_anterior=stock_anterior,
        stock_nuevo=stock_nuevo,
        motivo=data.motivo,
    )
    db.add(movimiento)
    db.commit()
    db.refresh(movimiento)

    return MovimientoStockPublico(
        id=movimiento.id,
        producto_id=producto.id,
        producto_nombre=producto.nombre,
        usuario_id=usuario.id,
        usuario_nombre=usuario.nombre,
        tipo=movimiento.tipo,
        cantidad=float(movimiento.cantidad),
        stock_anterior=float(movimiento.stock_anterior),
        stock_nuevo=float(movimiento.stock_nuevo),
        motivo=movimiento.motivo,
        creado_en=movimiento.creado_en,
    )


def listar_movimientos(
    db: Session,
    almacen_id: int,
    producto_id: int | None = None,
    limit: int = 50,
) -> list[MovimientoStockPublico]:
    stmt = (
        select(MovimientoStock, Producto.nombre, Usuario.nombre)
        .join(Producto, MovimientoStock.producto_id == Producto.id)
        .join(Usuario, MovimientoStock.usuario_id == Usuario.id)
        .where(Producto.almacen_id == almacen_id)
        .order_by(MovimientoStock.id.desc())
        .limit(limit)
    )
    if producto_id is not None:
        stmt = stmt.where(MovimientoStock.producto_id == producto_id)

    rows = db.execute(stmt).all()
    return [
        MovimientoStockPublico(
            id=mov.id,
            producto_id=mov.producto_id,
            producto_nombre=prod_nombre,
            usuario_id=mov.usuario_id,
            usuario_nombre=user_nombre,
            tipo=mov.tipo,
            cantidad=float(mov.cantidad),
            stock_anterior=float(mov.stock_anterior),
            stock_nuevo=float(mov.stock_nuevo),
            motivo=mov.motivo,
            creado_en=mov.creado_en,
        )
        for mov, prod_nombre, user_nombre in rows
    ]
