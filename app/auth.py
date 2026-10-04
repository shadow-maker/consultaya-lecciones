"""JWT HS256 (`iss: consultaya-usuarios`). `usuarios` emite; los demás servicios validan.

Claims: `sub` (UUID), `email`, `nombres`, `iat`, `exp`, `iss`.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import JWT_ALGORITMO, JWT_ISSUER, get_settings
from app.errors import ApiError

_esquema_bearer = HTTPBearer(auto_error=False, description="JWT emitido por `usuarios`.")


@dataclass(frozen=True)
class UsuarioToken:
    """Datos del usuario autenticado, tal como vienen en el token (sin consultar la base)."""

    id: UUID
    email: str
    nombres: str


def _no_autenticado(mensaje: str = "Debes iniciar sesión para continuar.") -> ApiError:
    return ApiError(401, "NO_AUTENTICADO", mensaje, headers={"WWW-Authenticate": "Bearer"})


def emitir_token(
    usuario_id: UUID | str,
    email: str,
    nombres: str,
    *,
    secret: str | None = None,
    exp_horas: float | None = None,
    ahora: datetime | None = None,
) -> str:
    """Emite un JWT con los claims del contrato.

    Lo usa `usuarios` en registro/login y los tests de los demás servicios. `exp_horas`
    negativo produce un token ya expirado (útil en tests).
    """
    settings = get_settings()
    emitido = ahora or datetime.now(UTC)
    horas = settings.jwt_exp_horas if exp_horas is None else exp_horas
    claims = {
        "sub": str(usuario_id),
        "email": email,
        "nombres": nombres,
        "iat": emitido,
        "exp": emitido + timedelta(hours=horas),
        "iss": JWT_ISSUER,
    }
    return jwt.encode(claims, secret or settings.jwt_secret, algorithm=JWT_ALGORITMO)


def validar_token(token: str) -> UsuarioToken:
    """Valida firma, `exp` e `iss`. Lanza `ApiError` 401 `NO_AUTENTICADO` si falla."""
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[JWT_ALGORITMO],  # fijo: evita ataques de confusión de algoritmo
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iss", "sub"]},
        )
        return UsuarioToken(
            id=UUID(str(claims["sub"])),
            email=str(claims.get("email", "")),
            nombres=str(claims.get("nombres", "")),
        )
    except jwt.ExpiredSignatureError:
        raise _no_autenticado("Tu sesión expiró. Inicia sesión de nuevo.") from None
    except (jwt.InvalidTokenError, ValueError):
        raise _no_autenticado() from None


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_esquema_bearer),
) -> UsuarioToken:
    """Dependencia de FastAPI para rutas protegidas: exige `Authorization: Bearer <JWT>`."""
    if credenciales is None or not credenciales.credentials:
        raise _no_autenticado()
    return validar_token(credenciales.credentials)
