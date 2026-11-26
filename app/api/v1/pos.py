from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_user
from app.models import Usuario
from app.schemas.pos import (
    AbrirCajaRequest,
    CrearVentaRequest,
    ProductoPosPublico,
    SesionCajaPublica,
    VentaPublica,
)
from app.services.pos_service import (
    abrir_caja,
    anular_venta,
    listar_productos_pos,
    listar_ventas,
    obtener_caja_abierta,
    registrar_venta,
    serializar_venta,
)

router = APIRouter(prefix="/api/v1/pos", tags=["POS"])


@router.get("/caja-actual", response_model=SesionCajaPublica | None)
def caja_actual(
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    caja = obtener_caja_abierta(db, usuario.almacen_id)
    if caja is None:
        return None
    return SesionCajaPublica.model_validate(caja)


@router.post(
    "/caja/abrir",
    response_model=SesionCajaPublica,
    status_code=status.HTTP_201_CREATED,
)
def abrir_turno_caja(
    data: AbrirCajaRequest,
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    caja = abrir_caja(db, usuario, data.fondo_inicial)
    return SesionCajaPublica.model_validate(caja)


@router.get("/productos", response_model=list[ProductoPosPublico])
def productos_pos(
    q: str | None = None,
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    return listar_productos_pos(db, usuario.almacen_id, q)


@router.post(
    "/ventas",
    response_model=VentaPublica,
    status_code=status.HTTP_201_CREATED,
)
def crear_venta(
    data: CrearVentaRequest,
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    venta = registrar_venta(db, usuario, data)
    return serializar_venta(venta)


@router.get("/ventas", response_model=list[VentaPublica])
def historial_ventas(
    solo_turno: bool = True,
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    ventas = listar_ventas(db, usuario.almacen_id, solo_turno=solo_turno)
    return [serializar_venta(v) for v in ventas]


@router.post("/ventas/{venta_id}/anular", response_model=VentaPublica)
def anular_venta_endpoint(
    venta_id: int,
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    venta = anular_venta(db, usuario, venta_id)
    return serializar_venta(venta)
