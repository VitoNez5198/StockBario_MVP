from datetime import timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Cookie, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import SESSION_COOKIE_NAME, read_session_token
from app.models import Almacen, RolUsuario, Usuario
from app.services.pos_service import obtener_caja_abierta, obtener_venta_con_detalle

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(include_in_schema=False)


def _get_session_user(
    db: Session,
    token: str | None,
) -> tuple[Usuario | None, Almacen | None]:
    if not token:
        return None, None
    payload = read_session_token(token)
    if not payload:
        return None, None
    usuario = db.scalar(
        select(Usuario).where(
            Usuario.id == payload["uid"],
            Usuario.almacen_id == payload["aid"],
            Usuario.activo.is_(True),
        )
    )
    if not usuario:
        return None, None
    almacen = db.get(Almacen, usuario.almacen_id)
    return usuario, almacen


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    db: Session = Depends(get_db),
    sb_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    usuario, _ = _get_session_user(db, sb_session)
    if usuario:
        return RedirectResponse(url="/", status_code=302)
    almacen = db.scalar(select(Almacen).where(Almacen.activo.is_(True)).limit(1))
    return templates.TemplateResponse(
        request,
        "login.html",
        {"almacen": almacen},
    )


@router.get("/", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
    sb_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    usuario, almacen = _get_session_user(db, sb_session)
    if not usuario:
        return RedirectResponse(url="/login", status_code=302)
    caja_abierta = obtener_caja_abierta(db, usuario.almacen_id)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "usuario": usuario,
            "almacen": almacen,
            "active_page": "dashboard",
            "caja_abierta": caja_abierta,
        },
    )


@router.get("/pos", response_class=HTMLResponse)
def pos_page(
    request: Request,
    db: Session = Depends(get_db),
    sb_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    usuario, almacen = _get_session_user(db, sb_session)
    if not usuario:
        return RedirectResponse(url="/login", status_code=302)
    caja_abierta = obtener_caja_abierta(db, usuario.almacen_id)
    return templates.TemplateResponse(
        request,
        "pos.html",
        {
            "usuario": usuario,
            "almacen": almacen,
            "active_page": "pos",
            "caja_abierta": caja_abierta,
        },
    )


def _formatear_fecha_chile(dt) -> str:
    try:
        tz = ZoneInfo("America/Santiago")
    except ZoneInfoNotFoundError:
        tz = timezone(timedelta(hours=-3))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).strftime("%d/%m/%Y %H:%M")


@router.get("/pos/ticket/{venta_id}", response_class=HTMLResponse)
def pos_ticket_page(
    venta_id: int,
    request: Request,
    embed: bool = False,
    db: Session = Depends(get_db),
    sb_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    usuario, almacen = _get_session_user(db, sb_session)
    if not usuario:
        return RedirectResponse(url="/login", status_code=302)
    venta = obtener_venta_con_detalle(db, usuario.almacen_id, venta_id)
    return templates.TemplateResponse(
        request,
        "ticket_80mm.html",
        {
            "usuario": usuario,
            "almacen": almacen,
            "venta": venta,
            "embed": embed,
            "fecha_local": _formatear_fecha_chile(venta.creada_en),
        },
    )


@router.get("/usuarios", response_class=HTMLResponse)
def usuarios_page(
    request: Request,
    db: Session = Depends(get_db),
    sb_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    usuario, almacen = _get_session_user(db, sb_session)
    if not usuario:
        return RedirectResponse(url="/login", status_code=302)
    if usuario.rol != RolUsuario.ADMIN.value:
        return RedirectResponse(url="/", status_code=302)
    caja_abierta = obtener_caja_abierta(db, usuario.almacen_id)
    return templates.TemplateResponse(
        request,
        "usuarios.html",
        {
            "usuario": usuario,
            "almacen": almacen,
            "active_page": "usuarios",
            "caja_abierta": caja_abierta,
        },
    )


MODULOS_SPRINT_2 = {
    "inventario": ("Inventario y Semaforo", "Control de existencias, vencimientos y mermas.", False),
    "fiados": ("Libreta de Fiados", "Cuentas corrientes de vecinos, cupos y abonos.", False),
    "compras": ("Compras Sugeridas", "Reposicion por proveedor lista para enviar por WhatsApp.", False),
    "caja": ("Caja y Arqueo Z", "Apertura de turno, medios de pago y cierre diario.", False),
    "reportes": ("Reportes Analiticos", "Rotacion de productos, margenes e indicadores ERI/TMV.", True),
}


@router.get("/{modulo}", response_class=HTMLResponse)
def modulo_page(
    modulo: str,
    request: Request,
    db: Session = Depends(get_db),
    sb_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    if modulo not in MODULOS_SPRINT_2:
        return RedirectResponse(url="/", status_code=302)
    usuario, almacen = _get_session_user(db, sb_session)
    if not usuario:
        return RedirectResponse(url="/login", status_code=302)

    titulo, descripcion, solo_admin = MODULOS_SPRINT_2[modulo]
    if solo_admin and usuario.rol != RolUsuario.ADMIN.value:
        return RedirectResponse(url="/", status_code=302)

    caja_abierta = obtener_caja_abierta(db, usuario.almacen_id)
    return templates.TemplateResponse(
        request,
        "modulo_pendiente.html",
        {
            "usuario": usuario,
            "almacen": almacen,
            "active_page": modulo,
            "titulo": titulo,
            "descripcion": descripcion,
            "caja_abierta": caja_abierta,
        },
    )
