from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EstadoCaja(str, Enum):
    ABIERTA = "ABIERTA"
    CERRADA = "CERRADA"


class MetodoPago(str, Enum):
    EFECTIVO = "EFECTIVO"
    DEBITO = "DEBITO"
    TRANSFERENCIA = "TRANSFERENCIA"
    FIADO = "FIADO"


class EstadoVenta(str, Enum):
    COMPLETADA = "COMPLETADA"
    ANULADA = "ANULADA"


class SesionCaja(Base):
    __tablename__ = "sesiones_caja"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    almacen_id: Mapped[int] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    usuario_apertura_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    usuario_cierre_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    fondo_inicial: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    efectivo_contado: Mapped[int | None] = mapped_column(Integer, nullable=True)
    diferencia: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estado: Mapped[str] = mapped_column(String(20), default=EstadoCaja.ABIERTA.value, nullable=False)
    abierta_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    cerrada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Venta(Base):
    __tablename__ = "ventas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    almacen_id: Mapped[int] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    sesion_caja_id: Mapped[int] = mapped_column(ForeignKey("sesiones_caja.id"), nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"), nullable=True)
    folio: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    metodo_pago: Mapped[str] = mapped_column(String(20), nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    monto_recibido: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vuelto: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), default=EstadoVenta.COMPLETADA.value, nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    usuario = relationship("Usuario")
    items = relationship("DetalleVenta", back_populates="venta", cascade="all, delete-orphan")


class DetalleVenta(Base):
    __tablename__ = "detalle_ventas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    venta_id: Mapped[int] = mapped_column(ForeignKey("ventas.id"), nullable=False, index=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"), nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    precio_costo_momento: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_venta_momento: Mapped[int] = mapped_column(Integer, nullable=False)
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)

    venta = relationship("Venta", back_populates="items")
    producto = relationship("Producto")
