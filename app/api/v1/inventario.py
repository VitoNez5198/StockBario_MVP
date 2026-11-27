from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin, require_user
from app.models import Usuario
from app.schemas.inventario import (
    ActualizarProductoRequest,
    CambiarEstadoProductoRequest,
    CategoriaPublica,
    CrearCategoriaRequest,
    CrearProductoRequest,
    MovimientoStockPublico,
    ProductoInventarioPublico,
    ProveedorPublico,
    RegistrarMovimientoRequest,
    ResumenInventarioPublico,
)
from app.services.inventario_service import (
    actualizar_producto,
    cambiar_estado_producto,
    crear_categoria,
    crear_producto,
    listar_categorias,
    listar_movimientos,
    listar_productos,
    listar_proveedores,
    obtener_resumen_inventario,
    registrar_movimiento_stock,
)

router = APIRouter(prefix="/api/v1/inventario", tags=["Inventario"])


@router.get("/resumen", response_model=ResumenInventarioPublico)
def resumen_inventario(
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    return obtener_resumen_inventario(db, usuario.almacen_id)


@router.get("/categorias", response_model=list[CategoriaPublica])
def get_categorias(
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    return listar_categorias(db, usuario.almacen_id)


@router.post(
    "/categorias",
    response_model=CategoriaPublica,
    status_code=status.HTTP_201_CREATED,
)
def post_categoria(
    data: CrearCategoriaRequest,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return crear_categoria(db, usuario, data)


@router.get("/proveedores", response_model=list[ProveedorPublico])
def get_proveedores(
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    return listar_proveedores(db, usuario.almacen_id)


@router.get("/productos", response_model=list[ProductoInventarioPublico])
def get_productos(
    q: str | None = None,
    categoria_id: int | None = None,
    estado_vencimiento: str | None = None,
    solo_stock_bajo: bool = False,
    incluir_inactivos: bool = False,
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    return listar_productos(
        db,
        usuario.almacen_id,
        q=q,
        categoria_id=categoria_id,
        estado_vencimiento=estado_vencimiento,
        solo_stock_bajo=solo_stock_bajo,
        incluir_inactivos=incluir_inactivos,
    )


@router.post(
    "/productos",
    response_model=ProductoInventarioPublico,
    status_code=status.HTTP_201_CREATED,
)
def post_producto(
    data: CrearProductoRequest,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return crear_producto(db, usuario, data)


@router.put("/productos/{producto_id}", response_model=ProductoInventarioPublico)
def put_producto(
    producto_id: int,
    data: ActualizarProductoRequest,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return actualizar_producto(db, usuario, producto_id, data)


@router.patch(
    "/productos/{producto_id}/estado",
    response_model=ProductoInventarioPublico,
)
def patch_estado_producto(
    producto_id: int,
    data: CambiarEstadoProductoRequest,
    usuario: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return cambiar_estado_producto(db, usuario, producto_id, data.activo)


@router.post(
    "/productos/{producto_id}/movimientos",
    response_model=MovimientoStockPublico,
    status_code=status.HTTP_201_CREATED,
)
def post_movimiento(
    producto_id: int,
    data: RegistrarMovimientoRequest,
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    return registrar_movimiento_stock(db, usuario, producto_id, data)


@router.get("/movimientos", response_model=list[MovimientoStockPublico])
def get_movimientos(
    producto_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    usuario: Usuario = Depends(require_user),
    db: Session = Depends(get_db),
):
    return listar_movimientos(db, usuario.almacen_id, producto_id=producto_id, limit=limit)
