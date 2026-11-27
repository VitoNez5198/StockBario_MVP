from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import hash_pin
from app.models import (
    Almacen,
    Categoria,
    Cliente,
    LoteProducto,
    Producto,
    Proveedor,
    RolUsuario,
    Usuario,
)


def _sync_missing_columns() -> None:
    inspector = inspect(engine)
    if "usuarios" in inspector.get_table_names():
        columnas = {col["name"] for col in inspector.get_columns("usuarios")}
        if "telefono" not in columnas:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE usuarios ADD COLUMN telefono VARCHAR(30)"))


def _seed_catalogo_inicial(db: Session, almacen_id: int) -> None:
    """Siembra categorias, proveedores y 6 productos base si el almacen no tiene catalogo."""
    existe_producto = db.scalar(
        select(Producto.id).where(Producto.almacen_id == almacen_id).limit(1)
    )
    if existe_producto is not None:
        return

    cat_pan = Categoria(almacen_id=almacen_id, nombre="Panaderia")
    cat_lac = Categoria(almacen_id=almacen_id, nombre="Lacteos")
    cat_beb = Categoria(almacen_id=almacen_id, nombre="Bebidas")
    db.add_all([cat_pan, cat_lac, cat_beb])

    prov_central = Proveedor(
        almacen_id=almacen_id,
        nombre="Distribuidora Central",
        telefono_whatsapp="+56991112222",
        contacto="Ventas Mayoristas",
    )
    prov_soprole = Proveedor(
        almacen_id=almacen_id,
        nombre="Soprole",
        telefono_whatsapp="+56982223333",
        contacto="Ruta Lunes y Jueves",
    )
    db.add_all([prov_central, prov_soprole])
    db.flush()

    hoy = date.today()
    productos = [
        Producto(
            almacen_id=almacen_id,
            categoria_id=cat_pan.id,
            proveedor_id=prov_central.id,
            codigo_barras="7801000100011",
            nombre="Pan Hallulla Granel",
            unidad="KG",
            precio_costo=1200,
            precio_venta=1850,
            stock_actual=Decimal("18.500"),
            stock_minimo=Decimal("5.000"),
            fecha_vencimiento=None,
        ),
        Producto(
            almacen_id=almacen_id,
            categoria_id=cat_lac.id,
            proveedor_id=prov_soprole.id,
            codigo_barras="7802900001012",
            nombre="Leche Entera 1L Soprole",
            unidad="UN",
            precio_costo=820,
            precio_venta=1190,
            stock_actual=Decimal("24"),
            stock_minimo=Decimal("8"),
            fecha_vencimiento=hoy + timedelta(days=35),
        ),
        Producto(
            almacen_id=almacen_id,
            categoria_id=cat_beb.id,
            proveedor_id=prov_central.id,
            codigo_barras="7801610001918",
            nombre="Coca-Cola Original 1.5L",
            unidad="UN",
            precio_costo=1350,
            precio_venta=1950,
            stock_actual=Decimal("18"),
            stock_minimo=Decimal("6"),
            fecha_vencimiento=hoy + timedelta(days=90),
        ),
        Producto(
            almacen_id=almacen_id,
            categoria_id=cat_pan.id,
            proveedor_id=prov_central.id,
            codigo_barras="7801900000386",
            nombre="Arroz Grado 1 1Kg",
            unidad="UN",
            precio_costo=1050,
            precio_venta=1590,
            stock_actual=Decimal("15"),
            stock_minimo=Decimal("5"),
            fecha_vencimiento=None,
        ),
        Producto(
            almacen_id=almacen_id,
            categoria_id=cat_lac.id,
            proveedor_id=prov_soprole.id,
            codigo_barras="7802900002057",
            nombre="Yogurt Batido Frutilla 125g",
            unidad="UN",
            precio_costo=240,
            precio_venta=390,
            stock_actual=Decimal("12"),
            stock_minimo=Decimal("6"),
            fecha_vencimiento=hoy + timedelta(days=4),
        ),
        Producto(
            almacen_id=almacen_id,
            categoria_id=cat_lac.id,
            proveedor_id=prov_soprole.id,
            codigo_barras="7802900004884",
            nombre="Queso Gauda Laminado 250g",
            unidad="PAQ",
            precio_costo=1950,
            precio_venta=2790,
            stock_actual=Decimal("4"),
            stock_minimo=Decimal("3"),
            fecha_vencimiento=hoy - timedelta(days=2),
        ),
    ]
    db.add_all(productos)


def _sync_lotes_iniciales(db: Session) -> None:
    productos = db.scalars(
        select(Producto).where(
            Producto.stock_actual > 0,
            Producto.fecha_vencimiento.is_not(None),
        )
    ).all()
    for prod in productos:
        existe_lote = db.scalar(
            select(LoteProducto.id).where(LoteProducto.producto_id == prod.id).limit(1)
        )
        if existe_lote is None:
            db.add(
                LoteProducto(
                    producto_id=prod.id,
                    cantidad_disponible=prod.stock_actual,
                    fecha_vencimiento=prod.fecha_vencimiento,
                )
            )


def _seed_clientes_iniciales(db: Session, almacen_id: int) -> None:
    existe = db.scalar(
        select(Cliente.id).where(Cliente.almacen_id == almacen_id).limit(1)
    )
    if existe is not None:
        return
    db.add_all(
        [
            Cliente(
                almacen_id=almacen_id,
                nombre="Sra. Rosa Morales",
                rut_o_apodo="Vecina Pasaje 3",
                telefono="+56991234567",
                direccion="Pasaje Los Aromos 114",
                limite_credito=30000,
                deuda_actual=0,
                activo=True,
            ),
            Cliente(
                almacen_id=almacen_id,
                nombre="Don Pedro Soto",
                rut_o_apodo="Maestro Taller",
                telefono="+56997654321",
                direccion="Av. Central 482",
                limite_credito=20000,
                deuda_actual=0,
                activo=True,
            ),
        ]
    )


def init_db() -> None:
    """Crea las tablas definidas y siembra datos iniciales si la BD esta vacia."""
    Base.metadata.create_all(bind=engine)
    _sync_missing_columns()

    settings = get_settings()
    with SessionLocal() as db:
        almacen = db.scalar(select(Almacen).limit(1))
        if almacen is None:
            almacen = Almacen(nombre=settings.default_store_name)
            db.add(almacen)
            db.flush()

        admin = db.scalar(
            select(Usuario).where(
                Usuario.almacen_id == almacen.id,
                Usuario.username == settings.default_admin_user,
            )
        )
        if admin is None:
            admin = Usuario(
                almacen_id=almacen.id,
                nombre="Administrador",
                username=settings.default_admin_user,
                pin_hash=hash_pin(settings.default_admin_pin),
                rol=RolUsuario.ADMIN.value,
            )
            db.add(admin)

        _seed_catalogo_inicial(db, almacen.id)
        _seed_clientes_iniciales(db, almacen.id)
        db.flush()
        _sync_lotes_iniciales(db)
        db.commit()
