from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.usuario import RolUsuario


class UsuarioPublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    almacen_id: int
    nombre: str
    username: str
    rol: str
    activo: bool


class LoginRequest(BaseModel):
    usuario_id: int = Field(..., gt=0)
    pin: str = Field(..., min_length=4, max_length=4)

    @field_validator("pin")
    @classmethod
    def validar_pin_numerico(cls, valor: str) -> str:
        limpio = valor.strip()
        if not (limpio.isdigit() and len(limpio) == 4):
            raise ValueError("El PIN debe tener 4 digitos numericos")
        return limpio


class CrearUsuarioRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=2, max_length=50)
    pin: str = Field(..., min_length=4, max_length=4)
    rol: RolUsuario = RolUsuario.CAJERO

    @field_validator("username")
    @classmethod
    def normalizar_username(cls, valor: str) -> str:
        return valor.strip().lower()

    @field_validator("pin")
    @classmethod
    def validar_pin_numerico(cls, valor: str) -> str:
        limpio = valor.strip()
        if not (limpio.isdigit() and len(limpio) == 4):
            raise ValueError("El PIN debe tener 4 digitos numericos")
        return limpio


class SesionResponse(BaseModel):
    mensaje: str
    usuario: UsuarioPublico
