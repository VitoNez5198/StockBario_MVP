from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoriaPublica(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str


class CrearCategoriaRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=80)

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, valor: str) -> str:
        limpio = valor.strip()
        if len(limpio) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return limpio


class ProveedorPublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    telefono_whatsapp: str | None = None
    contacto: str | None = None


class LoteProductoPublico(BaseModel):
    id: int
    cantidad_disponible: float
    fecha_vencimiento: date | None = None
    estado_vencimiento: Literal["SIN_FECHA", "OPTIMO", "POR_VENCER", "VENCIDO"]
    vencido: bool


class ProductoInventarioPublico(BaseModel):
    id: int
    codigo_barras: str | None = None
    nombre: str
    categoria_id: int | None = None
    categoria_nombre: str | None = None
    proveedor_id: int | None = None
    proveedor_nombre: str | None = None
    unidad: str
    precio_costo: int
    precio_venta: int
    stock_actual: float
    stock_vendible: float
    stock_vencido: float
    stock_minimo: float
    stock_bajo: bool
    fecha_vencimiento: date | None = None
    estado_vencimiento: Literal["SIN_FECHA", "OPTIMO", "POR_VENCER", "VENCIDO"]
    bloqueado_venta: bool
    activo: bool
    lotes: list[LoteProductoPublico] = Field(default_factory=list)


class ResumenInventarioPublico(BaseModel):
    total_activos: int
    total_inactivos: int
    stock_bajo: int
    por_vencer: int
    vencidos: int


class _ProductoBaseRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=150)
    codigo_barras: str | None = Field(default=None, max_length=50)
    categoria_id: int | None = Field(default=None, gt=0)
    proveedor_id: int | None = Field(default=None, gt=0)
    unidad: Literal["UN", "KG", "PAQ"] = "UN"
    precio_costo: int = Field(default=0, ge=0)
    precio_venta: int = Field(..., gt=0)
    stock_minimo: Decimal = Field(default=Decimal("5"), ge=0)
    fecha_vencimiento: date | None = None

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, valor: str) -> str:
        limpio = valor.strip()
        if len(limpio) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return limpio

    @field_validator("codigo_barras")
    @classmethod
    def limpiar_codigo(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        limpio = valor.strip()
        return limpio or None


class CrearProductoRequest(_ProductoBaseRequest):
    stock_actual: Decimal = Field(default=Decimal("0"), ge=0)


class ActualizarProductoRequest(_ProductoBaseRequest):
    pass


class CambiarEstadoProductoRequest(BaseModel):
    activo: bool


class RegistrarMovimientoRequest(BaseModel):
    tipo: Literal["ENTRADA", "MERMA", "AJUSTE"]
    cantidad: Decimal = Field(..., ge=0)
    motivo: str = Field(..., min_length=3, max_length=200)
    fecha_vencimiento: date | None = None
    lote_id: int | None = Field(default=None, gt=0)

    @field_validator("motivo")
    @classmethod
    def limpiar_motivo(cls, valor: str) -> str:
        limpio = valor.strip()
        if len(limpio) < 3:
            raise ValueError("El motivo debe tener al menos 3 caracteres")
        return limpio


class MovimientoStockPublico(BaseModel):
    id: int
    producto_id: int
    producto_nombre: str
    usuario_id: int
    usuario_nombre: str
    tipo: str
    cantidad: float
    stock_anterior: float
    stock_nuevo: float
    motivo: str | None = None
    creado_en: datetime
