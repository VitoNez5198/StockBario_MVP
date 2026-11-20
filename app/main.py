"""Punto de entrada principal de StockBarrio MVP (FastAPI)."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import check_database_connection

settings = get_settings()

app = FastAPI(
    title=f"{settings.app_name} API",
    description="Plataforma web SaaS de inventario y punto de venta para almacenes de barrio.",
    version="0.1.0",
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
        "message": "StockBarrio MVP inicializado. Próximo paso: módulos del Sprint 1.",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
