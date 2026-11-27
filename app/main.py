from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.auth import router as auth_router
from app.api.v1.compras import router as compras_router
from app.api.v1.fiados import router as fiados_router
from app.api.v1.inventario import router as inventario_router
from app.api.v1.pos import router as pos_router
from app.core.config import get_settings
from app.core.database import check_database_connection
from app.core.errors import register_error_handlers
from app.core.init_db import init_db
from app.web.routes import router as web_router

settings = get_settings()
STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=f"{settings.app_name} API",
    description="Plataforma web de inventario y punto de venta para almacenes de barrio.",
    version="0.1.0",
    lifespan=lifespan,
)

register_error_handlers(app)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(auth_router)
app.include_router(pos_router)
app.include_router(inventario_router)
app.include_router(fiados_router)
app.include_router(compras_router)


@app.get("/api/v1/health", tags=["Sistema"])
def healthcheck():
    db_ok, detail = check_database_connection()
    status_code = 200 if db_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if db_ok else "error",
            "app": settings.app_name,
            "env": settings.app_env,
            "database": detail if db_ok else "unreachable",
        },
    )


app.include_router(web_router)
