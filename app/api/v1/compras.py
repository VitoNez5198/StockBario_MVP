from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, require_user
from app.models import Usuario
from app.schemas.compras import (
    ActualizarProveedorRequest,
    CambiarEstadoProveedorRequest,
    CrearProveedorRequest,
    ProveedorDetallePublico,
    ResumenComprasSugeridas,
)
from app.services.compras_service import (
    actualizar_proveedor,
    cambiar_estado_proveedor,
    crear_proveedor,
    listar_proveedores_detalle,
    obtener_compras_sugeridas,
)

router = APIRouter(prefix="/api/v1/compras", tags=["Compras"])


@router.get("/sugeridas", response_model=ResumenComprasSugeridas)
def get_compras_sugeridas(
    incluir_todos: bool = False,
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    return obtener_compras_sugeridas(db, usuario.almacen_id, incluir_todos=incluir_todos)


@router.get("/proveedores", response_model=list[ProveedorDetallePublico])
def get_proveedores(
    incluir_inactivos: bool = False,
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    return listar_proveedores_detalle(
        db,
        usuario.almacen_id,
        incluir_inactivos=incluir_inactivos,
    )


@router.post(
    "/proveedores",
    response_model=ProveedorDetallePublico,
    status_code=status.HTTP_201_CREATED,
)
def post_proveedor(
    data: CrearProveedorRequest,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return crear_proveedor(db, usuario, data)


@router.put("/proveedores/{proveedor_id}", response_model=ProveedorDetallePublico)
def put_proveedor(
    proveedor_id: int,
    data: ActualizarProveedorRequest,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return actualizar_proveedor(db, usuario, proveedor_id, data)


@router.patch("/proveedores/{proveedor_id}/estado", response_model=ProveedorDetallePublico)
def patch_estado_proveedor(
    proveedor_id: int,
    data: CambiarEstadoProveedorRequest,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return cambiar_estado_proveedor(db, usuario, proveedor_id, data.activo)
