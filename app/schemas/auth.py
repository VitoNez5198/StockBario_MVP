import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.usuario import RolUsuario

NOMBRE_REGEX = re.compile(r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü\s'-]+$")
USERNAME_REGEX = re.compile(r"^[a-z0-9._-]+$")
TELEFONO_REGEX = re.compile(r"^[0-9+\s()-]{6,30}$")


def _validar_nombre(valor: str) -> str:
    limpio = " ".join(valor.strip().split())
    if len(limpio) < 2:
        raise ValueError("El nombre debe tener al menos 2 caracteres")
    if not NOMBRE_REGEX.match(limpio):
        raise ValueError("El nombre solo puede contener letras y espacios")
    return limpio


def _validar_telefono(valor: str | None) -> str | None:
    if valor is None:
        return None
    limpio = valor.strip()
    if not limpio:
        return None
    if not TELEFONO_REGEX.match(limpio):
        raise ValueError("Telefono invalido (usa solo numeros, espacios o +)")
    return limpio


def _validar_pin(valor: str) -> str:
    limpio = valor.strip()
    if not (limpio.isdigit() and len(limpio) == 4):
        raise ValueError("El PIN debe tener 4 digitos numericos")
    return limpio


class UsuarioPublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    almacen_id: int
    nombre: str
    username: str
    telefono: str | None = None
    rol: str
    activo: bool


class LoginRequest(BaseModel):
    usuario_id: int = Field(..., gt=0)
    pin: str = Field(..., min_length=4, max_length=4)

    @field_validator("pin")
    @classmethod
    def validar_pin_numerico(cls, valor: str) -> str:
        return _validar_pin(valor)


class CrearUsuarioRequest(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    username: str = Field(..., min_length=2, max_length=50)
    telefono: str | None = Field(default=None, max_length=30)
    pin: str = Field(..., min_length=4, max_length=4)
    rol: RolUsuario = RolUsuario.CAJERO

    @field_validator("nombre")
    @classmethod
    def validar_nombre_letras(cls, valor: str) -> str:
        return _validar_nombre(valor)

    @field_validator("username")
    @classmethod
    def normalizar_username(cls, valor: str) -> str:
        limpio = valor.strip().lower()
        if not USERNAME_REGEX.match(limpio):
            raise ValueError("El usuario solo permite letras, numeros, punto o guion")
        return limpio

    @field_validator("telefono")
    @classmethod
    def validar_telefono_opcional(cls, valor: str | None) -> str | None:
        return _validar_telefono(valor)

    @field_validator("pin")
    @classmethod
    def validar_pin_numerico(cls, valor: str) -> str:
        return _validar_pin(valor)


class ActualizarUsuarioRequest(BaseModel):
    nombre: str | None = Field(default=None, min_length=2, max_length=100)
    telefono: str | None = Field(default=None, max_length=30)
    rol: RolUsuario | None = None
    pin: str | None = Field(default=None, min_length=4, max_length=4)
    activo: bool | None = None

    @field_validator("nombre")
    @classmethod
    def validar_nombre_opcional(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        return _validar_nombre(valor)

    @field_validator("telefono")
    @classmethod
    def validar_telefono_opcional(cls, valor: str | None) -> str | None:
        return _validar_telefono(valor)

    @field_validator("pin")
    @classmethod
    def validar_pin_opcional(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        return _validar_pin(valor)


class SesionResponse(BaseModel):
    mensaje: str
    usuario: UsuarioPublico
