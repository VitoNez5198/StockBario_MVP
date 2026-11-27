from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, require_user
from app.models import Usuario
from app.schemas.fiados import (
    AbonoPublico,
    ActualizarClienteRequest,
    CambiarEstadoClienteRequest,
    ClientePublico,
    CrearClienteRequest,
    MovimientoClientePublico,
    RegistrarAbonoRequest,
    ResumenFiadosPublico,
)
from app.services.fiados_service import (
    actualizar_cliente,
    cambiar_estado_cliente,
    crear_cliente,
    listar_clientes,
    listar_movimientos_cliente,
    obtener_resumen_fiados,
    registrar_abono,
)

router = APIRouter(prefix="/api/v1/fiados", tags=["Fiados"])


@router.get("/resumen", response_model=ResumenFiadosPublico)
def resumen_fiados(
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    return obtener_resumen_fiados(db, usuario.almacen_id)


@router.get("/clientes", response_model=list[ClientePublico])
def get_clientes(
    q: str | None = None,
    solo_con_deuda: bool = False,
    incluir_inactivos: bool = False,
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    return listar_clientes(
        db,
        usuario.almacen_id,
        q=q,
        solo_con_deuda=solo_con_deuda,
        incluir_inactivos=incluir_inactivos,
    )


@router.post(
    "/clientes",
    response_model=ClientePublico,
    status_code=status.HTTP_201_CREATED,
)
def post_cliente(
    data: CrearClienteRequest,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return crear_cliente(db, usuario, data)


@router.put("/clientes/{cliente_id}", response_model=ClientePublico)
def put_cliente(
    cliente_id: int,
    data: ActualizarClienteRequest,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return actualizar_cliente(db, usuario, cliente_id, data)


@router.patch("/clientes/{cliente_id}/estado", response_model=ClientePublico)
def patch_estado_cliente(
    cliente_id: int,
    data: CambiarEstadoClienteRequest,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return cambiar_estado_cliente(db, usuario, cliente_id, data.activo)


@router.post(
    "/clientes/{cliente_id}/abonos",
    response_model=AbonoPublico,
    status_code=status.HTTP_201_CREATED,
)
def post_abono(
    cliente_id: int,
    data: RegistrarAbonoRequest,
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    return registrar_abono(db, usuario, cliente_id, data)


@router.get(
    "/clientes/{cliente_id}/movimientos",
    response_model=list[MovimientoClientePublico],
)
def get_movimientos_cliente(
    cliente_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    return listar_movimientos_cliente(db, usuario.almacen_id, cliente_id, limit=limit)
