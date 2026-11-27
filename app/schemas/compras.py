from pydantic import BaseModel, ConfigDict, Field, field_validator


def _limpiar_opcional(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpio = valor.strip()
    return limpio or None


class ProveedorDetallePublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    telefono_whatsapp: str | None = None
    contacto: str | None = None
    activo: bool
    productos_asociados: int = 0


class _ProveedorBaseRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120)
    telefono_whatsapp: str | None = Field(default=None, max_length=30)
    contacto: str | None = Field(default=None, max_length=100)

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, valor: str) -> str:
        limpio = valor.strip()
        if len(limpio) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return limpio

    @field_validator("telefono_whatsapp", "contacto")
    @classmethod
    def limpiar_campos(cls, valor: str | None) -> str | None:
        return _limpiar_opcional(valor)


class CrearProveedorRequest(_ProveedorBaseRequest):
    pass


class ActualizarProveedorRequest(_ProveedorBaseRequest):
    pass


class CambiarEstadoProveedorRequest(BaseModel):
    activo: bool


class ItemCompraSugerida(BaseModel):
    producto_id: int
    nombre: str
    codigo_barras: str | None = None
    unidad: str
    stock_vendible: float
    stock_minimo: float
    cantidad_sugerida: float
    precio_costo: int
    subtotal_estimado: int
    estado_vencimiento: str


class GrupoCompraSugerida(BaseModel):
    proveedor_id: int | None = None
    proveedor_nombre: str
    telefono_whatsapp: str | None = None
    contacto: str | None = None
    total_items: int
    costo_estimado: int
    mensaje_whatsapp: str
    whatsapp_url: str | None = None
    items: list[ItemCompraSugerida]


class ResumenComprasSugeridas(BaseModel):
    total_productos_reponer: int
    total_grupos: int
    costo_total_estimado: int
    grupos: list[GrupoCompraSugerida]
