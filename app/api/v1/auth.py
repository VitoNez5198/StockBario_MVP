from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import require_admin, require_user
from app.core.security import (
    SESSION_COOKIE_NAME,
    create_session_token,
    hash_pin,
    verify_pin,
)
from app.models import Almacen, RolUsuario, Usuario
from app.schemas.auth import (
    ActualizarUsuarioRequest,
    CrearUsuarioRequest,
    LoginRequest,
    SesionResponse,
    UsuarioPublico,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticacion"])


@router.get("/usuarios", response_model=list[UsuarioPublico])
def listar_usuarios_almacen(
    almacen_id: int | None = None,
    db: Session = Depends(get_db),
):
    if almacen_id is None:
        almacen = db.scalar(select(Almacen).where(Almacen.activo.is_(True)).limit(1))
        if not almacen:
            return []
        almacen_id = almacen.id

    usuarios = db.scalars(
        select(Usuario)
        .where(Usuario.almacen_id == almacen_id, Usuario.activo.is_(True))
        .order_by(Usuario.id.asc())
    ).all()
    return list(usuarios)


@router.post("/login", response_model=SesionResponse)
def iniciar_sesion(
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    usuario = db.scalar(
        select(Usuario).where(
            Usuario.id == data.usuario_id,
            Usuario.activo.is_(True),
        )
    )
    if not usuario or not verify_pin(data.pin, usuario.pin_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o PIN incorrecto",
        )

    settings = get_settings()
    token = create_session_token(usuario.id, usuario.almacen_id, usuario.rol)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=not settings.debug,
        max_age=settings.session_expire_hours * 3600,
    )
    return SesionResponse(
        mensaje="Sesion iniciada",
        usuario=UsuarioPublico.model_validate(usuario),
    )


@router.post("/logout")
def cerrar_sesion(response: Response):
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return {"mensaje": "Sesion cerrada"}


@router.get("/me", response_model=UsuarioPublico)
def usuario_actual(usuario: Usuario = Depends(require_user)):
    return UsuarioPublico.model_validate(usuario)


@router.post(
    "/usuarios",
    response_model=UsuarioPublico,
    status_code=status.HTTP_201_CREATED,
)
def crear_usuario(
    data: CrearUsuarioRequest,
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    existente = db.scalar(
        select(Usuario).where(
            Usuario.almacen_id == admin.almacen_id,
            Usuario.username == data.username,
        )
    )
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese nombre en este almacen",
        )

    nuevo = Usuario(
        almacen_id=admin.almacen_id,
        nombre=data.nombre,
        username=data.username,
        telefono=data.telefono,
        pin_hash=hash_pin(data.pin),
        rol=data.rol.value,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return UsuarioPublico.model_validate(nuevo)


def _contar_admins_activos(db: Session, almacen_id: int) -> int:
    total = db.scalar(
        select(func.count(Usuario.id)).where(
            Usuario.almacen_id == almacen_id,
            Usuario.rol == RolUsuario.ADMIN.value,
            Usuario.activo.is_(True),
        )
    )
    return int(total or 0)


@router.get("/usuarios/admin", response_model=list[UsuarioPublico])
def listar_todos_los_usuarios(
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    usuarios = db.scalars(
        select(Usuario)
        .where(Usuario.almacen_id == admin.almacen_id)
        .order_by(Usuario.id.asc())
    ).all()
    return list(usuarios)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioPublico)
def actualizar_usuario(
    usuario_id: int,
    data: ActualizarUsuarioRequest,
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    objetivo = db.scalar(
        select(Usuario).where(
            Usuario.id == usuario_id,
            Usuario.almacen_id == admin.almacen_id,
        )
    )
    if not objetivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    if objetivo.id == admin.id and data.activo is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propio usuario",
        )

    es_admin_activo = objetivo.rol == RolUsuario.ADMIN.value and objetivo.activo
    pierde_admin = (
        (data.rol is not None and data.rol != RolUsuario.ADMIN)
        or data.activo is False
    )
    if es_admin_activo and pierde_admin and _contar_admins_activos(db, admin.almacen_id) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe existir al menos un administrador activo en el almacen",
        )

    campos_enviados = data.model_fields_set
    if "nombre" in campos_enviados and data.nombre is not None:
        objetivo.nombre = data.nombre
    if "telefono" in campos_enviados:
        objetivo.telefono = data.telefono
    if "rol" in campos_enviados and data.rol is not None:
        objetivo.rol = data.rol.value
    if "pin" in campos_enviados and data.pin is not None:
        objetivo.pin_hash = hash_pin(data.pin)
    if "activo" in campos_enviados and data.activo is not None:
        objetivo.activo = data.activo

    db.commit()
    db.refresh(objetivo)
    return UsuarioPublico.model_validate(objetivo)


@router.delete("/usuarios/{usuario_id}")
def eliminar_usuario(
    usuario_id: int,
    admin: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    objetivo = db.scalar(
        select(Usuario).where(
            Usuario.id == usuario_id,
            Usuario.almacen_id == admin.almacen_id,
        )
    )
    if not objetivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )

    if objetivo.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu propio usuario",
        )

    if (
        objetivo.rol == RolUsuario.ADMIN.value
        and objetivo.activo
        and _contar_admins_activos(db, admin.almacen_id) <= 1
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe existir al menos un administrador activo en el almacen",
        )

    db.delete(objetivo)
    db.commit()
    return {"mensaje": "Usuario eliminado"}
