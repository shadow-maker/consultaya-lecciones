"""Schemas Pydantic (request/response)."""

from pydantic import BaseModel


class SaludOut(BaseModel):
    status: str = "ok"
    servicio: str


class ErrorDetalle(BaseModel):
    codigo: str
    mensaje: str
    campos: dict[str, str] | None = None


class ErrorOut(BaseModel):
    """Formato de error estándar (ver `docs/02-contratos-api.md`)."""

    error: ErrorDetalle
