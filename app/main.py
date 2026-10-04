"""Aplicación FastAPI del servicio (nombre, prefijo y puerto: ver `app/config.py`)."""

import logging

from fastapi import FastAPI

from app.config import PREFIJO, SERVICIO, get_settings
from app.errors import registrar_manejadores
from app.routers import health


def create_app() -> FastAPI:
    logging.basicConfig(
        level=get_settings().log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = FastAPI(
        title=f"ConsultaYa · {SERVICIO}",
        version="0.1.0",
        docs_url=f"{PREFIJO}/docs",
        redoc_url=f"{PREFIJO}/redoc",
        openapi_url=f"{PREFIJO}/openapi.json",
    )
    registrar_manejadores(app)

    app.include_router(health.router_raiz)
    app.include_router(health.router, prefix=PREFIJO)
    # Routers de dominio: app.include_router(<modulo>.router, prefix=PREFIJO)
    # Rutas internas (solo red Docker): app.include_router(<modulo>.router_interno)  # /interno/...
    return app


app = create_app()
