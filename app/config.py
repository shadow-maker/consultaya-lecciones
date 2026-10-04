"""Configuración del servicio.

Para adaptar la plantilla a otro microservicio basta con cambiar las constantes de la
sección "Identidad del servicio" (y las variables de entorno de `.env`).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Identidad del servicio (único lugar a cambiar al copiar la plantilla) -----------------
SERVICIO = "lecciones"  # 'usuarios' | 'lecciones' | 'progreso'
PUERTO_LOCAL = 8002  # 8001 usuarios · 8002 lecciones · 8003 progreso (en Docker siempre 8000)

# --- Derivados (no tocar) -------------------------------------------------------------------
PREFIJO = f"/api/{SERVICIO}"

# --- JWT (iguales en los 3 servicios: el emisor siempre es `usuarios`) ----------------------
JWT_ALGORITMO = "HS256"
JWT_ISSUER = "consultaya-usuarios"


class Settings(BaseSettings):
    """Variables de entorno (o `.env`). Los nombres en minúscula equivalen a MAYÚSCULA."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    test_database_url: str | None = None
    jwt_secret: str
    jwt_exp_horas: int = 24  # solo `usuarios` emite; aquí lo usa `emitir_token` en tests
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # los valores salen del entorno
