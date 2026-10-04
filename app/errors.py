"""Formato de error estándar de todos los servicios.

    {"error": {"codigo": "CORREO_EN_USO", "mensaje": "...", "campos": null}}

Uso en endpoints:  `raise ApiError(409, "CORREO_EN_USO", "Este correo ya está en uso.")`.
En validadores Pydantic, un `ValueError("Mensaje en español")` se convierte en el mensaje del
campo dentro de `campos` (422 `VALIDACION`).
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Error de negocio con código y mensaje en español."""

    def __init__(
        self,
        status_code: int,
        codigo: str,
        mensaje: str,
        campos: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.status_code = status_code
        self.codigo = codigo
        self.mensaje = mensaje
        self.campos = campos
        self.headers = headers


def respuesta_error(
    status_code: int,
    codigo: str,
    mensaje: str,
    campos: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"codigo": codigo, "mensaje": mensaje, "campos": campos}},
        headers=headers,
    )


# Códigos por defecto para HTTPException "genéricas" (p. ej. 404 de ruta inexistente).
_HTTP_GENERICOS: dict[int, tuple[str, str]] = {
    400: ("SOLICITUD_INVALIDA", "La solicitud no es válida."),
    401: ("NO_AUTENTICADO", "Debes iniciar sesión para continuar."),
    403: ("PROHIBIDO", "No tienes permiso para realizar esta acción."),
    404: ("NO_ENCONTRADO", "No se encontró el recurso solicitado."),
    405: ("METODO_NO_PERMITIDO", "Método no permitido para este recurso."),
    503: ("SERVICIO_NO_DISPONIBLE", "El servicio no está disponible por ahora."),
}

# Mensajes en español para los tipos de error de Pydantic más comunes.
_MENSAJES_PYDANTIC: dict[str, str] = {
    "missing": "Este campo es obligatorio.",
    "string_type": "Debe ser un texto.",
    "int_type": "Debe ser un número entero.",
    "int_parsing": "Debe ser un número entero.",
    "float_type": "Debe ser un número.",
    "float_parsing": "Debe ser un número.",
    "bool_type": "Debe ser verdadero o falso.",
    "uuid_parsing": "Debe ser un identificador válido.",
    "string_too_short": "El texto es demasiado corto.",
    "string_too_long": "El texto es demasiado largo.",
    "value_error": "El valor no es válido.",
}


def _campo_y_mensaje(error: dict[str, Any]) -> tuple[str, str]:
    loc = [str(parte) for parte in error.get("loc", ())]
    tipo = error.get("type", "")
    if tipo == "json_invalid":
        return "cuerpo", "El cuerpo de la solicitud no es un JSON válido."
    # loc empieza con 'body' | 'query' | 'path' | 'header' | 'cookie'.
    partes = loc[1:] if loc and loc[0] in {"body", "query", "path", "header", "cookie"} else loc
    if not partes:
        if tipo == "missing":
            return "cuerpo", "Falta el cuerpo de la solicitud."
        return "cuerpo", "El cuerpo de la solicitud no es válido."
    campo = ".".join(partes)
    if tipo in {"value_error", "assertion_error"}:
        # Los validadores del proyecto lanzan ValueError("<mensaje en español>").
        causa = (error.get("ctx") or {}).get("error")
        if causa is not None and str(causa):
            return campo, str(causa)
    return campo, _MENSAJES_PYDANTIC.get(tipo, "El valor no es válido.")


def campos_desde_validacion(errores: list[dict[str, Any]]) -> dict[str, str]:
    """Convierte errores de Pydantic en `{campo: mensaje}` (se conserva el primero por campo)."""
    campos: dict[str, str] = {}
    for error in errores:
        campo, mensaje = _campo_y_mensaje(error)
        campos.setdefault(campo, mensaje)
    return campos


async def _manejar_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return respuesta_error(exc.status_code, exc.codigo, exc.mensaje, exc.campos, exc.headers)


async def _manejar_validacion(request: Request, exc: RequestValidationError) -> JSONResponse:
    return respuesta_error(
        422,
        "VALIDACION",
        "Revisa los datos ingresados.",
        campos_desde_validacion(list(exc.errors())),
    )


async def _manejar_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    codigo, mensaje = _HTTP_GENERICOS.get(
        exc.status_code,
        (
            "ERROR_INTERNO" if exc.status_code >= 500 else "ERROR_HTTP",
            "No se pudo procesar la solicitud.",
        ),
    )
    return respuesta_error(exc.status_code, codigo, mensaje, headers=getattr(exc, "headers", None))


async def _manejar_inesperado(request: Request, exc: Exception) -> JSONResponse:
    # El detalle va solo al log; la respuesta nunca incluye stack trace.
    logger.error("Error no controlado en %s %s", request.method, request.url.path, exc_info=exc)
    return respuesta_error(500, "ERROR_INTERNO", "Ocurrió un error inesperado. Inténtalo de nuevo.")


def registrar_manejadores(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _manejar_api_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _manejar_validacion)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _manejar_http)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _manejar_inesperado)
