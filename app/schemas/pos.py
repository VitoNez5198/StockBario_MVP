from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.venta import MetodoPago


class AbrirCajaRequest(BaseModel):
    fondo_inicial: int = Field(default=0, ge=0)


class SesionCajaPublica(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fondo_inicial: int
    estado: str
    abierta_en: datetime
    usuario_apertura_id: int


class ProductoPosPublico(BaseModel):
    id: int
    codigo_barras: str | None = None
    nombre: str
    unidad: str
    precio_venta: int
    stock_actual: float
    stock_minimo: float
    fecha_vencimiento: date | None = None
    estado_vencimiento: Literal["SIN_FECHA", "OPTIMO", "POR_VENCER", "VENCIDO"]
    bloqueado_venta: bool


class ItemVentaRequest(BaseModel):
    producto_id: int = Field(..., gt=0)
    cantidad: Decimal = Field(..., gt=0)


class CrearVentaRequest(BaseModel):
    metodo_pago: MetodoPago
    items: list[ItemVentaRequest] = Field(..., min_length=1)
    monto_recibido: int | None = Field(default=None, ge=0)
    cliente_id: int | None = Field(default=None, gt=0)


class DetalleVentaPublico(BaseModel):
    id: int
    producto_id: int
    producto_nombre: str
    cantidad: float
    precio_venta_momento: int
    subtotal: int


class VentaPublica(BaseModel):
    id: int
    folio: str
    sesion_caja_id: int
    usuario_id: int
    usuario_nombre: str
    cliente_id: int | None = None
    metodo_pago: str
    total: int
    monto_recibido: int | None = None
    vuelto: int
    estado: str
    creada_en: datetime
    items: list[DetalleVentaPublico]
