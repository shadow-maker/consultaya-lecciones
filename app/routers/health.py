"""Health checks: `GET /health` y `GET /api/<servicio>/health`."""

from fastapi import APIRouter

from app.config import SERVICIO
from app.schemas import SaludOut

# `/health` (sin prefijo; lo usan Docker y nginx). Se oculta del OpenAPI para no duplicar.
router_raiz = APIRouter(include_in_schema=False)
# `/api/<servicio>/health` (se monta con el prefijo en `main.py`).
router = APIRouter(tags=["salud"])


@router_raiz.get("/health")
def salud_raiz() -> SaludOut:
    return SaludOut(servicio=SERVICIO)


@router.get("/health", summary="Estado del servicio")
def salud() -> SaludOut:
    return SaludOut(servicio=SERVICIO)
