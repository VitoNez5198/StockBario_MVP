from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": str(exc.detail),
                "codigo": exc.status_code,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError):
        detalles = []
        for err in exc.errors():
            ubicacion = [str(parte) for parte in err.get("loc", []) if parte != "body"]
            campo = ".".join(ubicacion) if ubicacion else "solicitud"
            detalles.append(
                {
                    "campo": campo,
                    "mensaje": err.get("msg", "Valor invalido"),
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": "Datos de entrada invalidos",
                "codigo": 422,
                "detalles": detalles,
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(_request: Request, _exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Error interno del servidor",
                "codigo": 500,
            },
        )
