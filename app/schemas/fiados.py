from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _limpiar_opcional(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpio = valor.strip()
    return limpio or None


class ClientePublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    rut_o_apodo: str | None = None
    telefono: str | None = None
    direccion: str | None = None
    limite_credito: int
    deuda_actual: int
    cupo_disponible: int
    porcentaje_uso: float
    activo: bool


class ResumenFiadosPublico(BaseModel):
    total_clientes_activos: int
    clientes_con_deuda: int
    deuda_total: int
    cupo_total: int


class _ClienteBaseRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120)
    rut_o_apodo: str | None = Field(default=None, max_length=40)
    telefono: str | None = Field(default=None, max_length=30)
    direccion: str | None = Field(default=None, max_length=200)
    limite_credito: int = Field(default=0, ge=0)

    @field_validator("nombre")
    @classmethod
    def limpiar_nombre(cls, valor: str) -> str:
        limpio = valor.strip()
        if len(limpio) < 2:
            raise ValueError("El nombre debe tener al menos 2 caracteres")
        return limpio

    @field_validator("rut_o_apodo", "telefono", "direccion")
    @classmethod
    def limpiar_campos_opcionales(cls, valor: str | None) -> str | None:
        return _limpiar_opcional(valor)


class CrearClienteRequest(_ClienteBaseRequest):
    pass


class ActualizarClienteRequest(_ClienteBaseRequest):
    pass


class CambiarEstadoClienteRequest(BaseModel):
    activo: bool


class RegistrarAbonoRequest(BaseModel):
    monto: int = Field(..., gt=0)
    metodo_pago: Literal["EFECTIVO", "DEBITO", "TRANSFERENCIA"] = "EFECTIVO"
    observacion: str | None = Field(default=None, max_length=200)

    @field_validator("observacion")
    @classmethod
    def limpiar_obs(cls, valor: str | None) -> str | None:
        return _limpiar_opcional(valor)


class AbonoPublico(BaseModel):
    id: int
    cliente_id: int
    sesion_caja_id: int
    usuario_id: int
    usuario_nombre: str
    monto: int
    metodo_pago: str
    observacion: str | None = None
    creado_en: datetime
    deuda_restante: int


class MovimientoClientePublico(BaseModel):
    tipo: Literal["FIADO", "ANULACION_FIADO", "ABONO"]
    fecha: datetime
    monto: int
    referencia: str
    detalle: str
    usuario_nombre: str
