from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TipoMovimiento(str, Enum):
    ENTRADA = "ENTRADA"
    VENTA = "VENTA"
    MERMA = "MERMA"
    AJUSTE = "AJUSTE"
    ANULACION = "ANULACION"


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    almacen_id: Mapped[int] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)

    productos = relationship("Producto", back_populates="categoria")


class Proveedor(Base):
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    almacen_id: Mapped[int] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    telefono_whatsapp: Mapped[str | None] = mapped_column(String(30), nullable=True)
    contacto: Mapped[str | None] = mapped_column(String(100), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    productos = relationship("Producto", back_populates="proveedor")


class Producto(Base):
    __tablename__ = "productos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    almacen_id: Mapped[int] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categorias.id"), nullable=True)
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id"), nullable=True)
    codigo_barras: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    unidad: Mapped[str] = mapped_column(String(10), default="UN", nullable=False)
    precio_costo: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_venta: Mapped[int] = mapped_column(Integer, nullable=False)
    stock_actual: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("0"), nullable=False)
    stock_minimo: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal("5"), nullable=False)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    categoria = relationship("Categoria", back_populates="productos")
    proveedor = relationship("Proveedor", back_populates="productos")
    lotes = relationship("LoteProducto", back_populates="producto", cascade="all, delete-orphan")


class LoteProducto(Base):
    __tablename__ = "lotes_producto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"), nullable=False, index=True)
    cantidad_disponible: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    producto = relationship("Producto", back_populates="lotes")


class MovimientoStock(Base):
    __tablename__ = "movimientos_stock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    stock_anterior: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    stock_nuevo: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    motivo: Mapped[str | None] = mapped_column(String(200), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
