from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import check_database_connection
from app.core.init_db import init_db

settings = get_settings()


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


@app.get("/", tags=["Sistema"])
def root():
    return {
        "app": settings.app_name,
        "message": "StockBarrio API operativa",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
