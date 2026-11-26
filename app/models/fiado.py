from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    almacen_id: Mapped[int] = mapped_column(ForeignKey("almacenes.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    rut_o_apodo: Mapped[str | None] = mapped_column(String(40), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    limite_credito: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deuda_actual: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AbonoFiado(Base):
    __tablename__ = "abonos_fiado"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), nullable=False, index=True)
    sesion_caja_id: Mapped[int] = mapped_column(ForeignKey("sesiones_caja.id"), nullable=False)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    monto: Mapped[int] = mapped_column(Integer, nullable=False)
    metodo_pago: Mapped[str] = mapped_column(String(20), nullable=False)
    observacion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
