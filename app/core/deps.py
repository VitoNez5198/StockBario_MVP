from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import SESSION_COOKIE_NAME, read_session_token
from app.models import RolUsuario, Usuario


def require_user(
    db: Session = Depends(get_db),
    sb_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> Usuario:
    payload = read_session_token(sb_session or "")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion no iniciada o expirada",
        )

    usuario = db.scalar(
        select(Usuario).where(
            Usuario.id == payload["uid"],
            Usuario.almacen_id == payload["aid"],
            Usuario.activo.is_(True),
        )
    )
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no valido o inactivo",
        )
    return usuario


def require_admin(usuario: Usuario = Depends(require_user)) -> Usuario:
    if usuario.rol != RolUsuario.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permiso denegado: solo administradores",
        )
    return usuario
