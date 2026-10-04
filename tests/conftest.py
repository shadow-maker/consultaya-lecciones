"""Fixtures de pytest: Postgres real (base `*_test`), esquema por Alembic y limpieza por test."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Valores locales por defecto, antes de importar `app` (un `.env` o el entorno los pisan).
os.environ.setdefault(
    "TEST_DATABASE_URL", "postgresql+psycopg://ca@localhost:5432/consultaya_lecciones_test"
)
os.environ.setdefault("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
os.environ.setdefault("JWT_SECRET", "dev-secret-cambiar")

from alembic.config import Config  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import Engine, create_engine, text  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from alembic import command  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import get_db  # noqa: E402
from app.main import create_app  # noqa: E402

SQL_TABLAS = (
    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
)
RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = get_settings().test_database_url
    assert url, "Define TEST_DATABASE_URL (ver .env.example)."
    nombre_bd = url.rsplit("/", 1)[-1].split("?")[0]
    # Protección: este fixture BORRA el esquema; solo se permite sobre bases `_test`.
    assert nombre_bd.startswith("consultaya_") and nombre_bd.endswith("_test"), (
        f"TEST_DATABASE_URL debe apuntar a una base consultaya_*_test, no a {nombre_bd!r}."
    )
    motor = create_engine(url, isolation_level="AUTOCOMMIT")
    with motor.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    yield motor
    motor.dispose()


@pytest.fixture(autouse=True)
def limpiar_tablas(engine: Engine) -> Iterator[None]:
    """TRUNCATE de todas las tablas de dominio antes de cada test."""
    with engine.connect() as conn:
        tablas = conn.execute(text(SQL_TABLAS)).scalars().all()
        if tablas:
            lista = ", ".join(f'"{t}"' for t in tablas)
            conn.execute(text(f"TRUNCATE {lista} RESTART IDENTITY CASCADE"))
        conn.commit()
    yield


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    with sessionmaker(bind=engine, expire_on_commit=False)() as sesion:
        yield sesion


@pytest.fixture
def app(engine: Engine) -> FastAPI:
    """App nueva por test (los tests pueden añadirle rutas propias) usando la base de pruebas."""
    aplicacion = create_app()
    fabrica = sessionmaker(bind=engine, expire_on_commit=False)

    def _get_db_test() -> Iterator[Session]:
        with fabrica() as sesion:
            yield sesion

    aplicacion.dependency_overrides[get_db] = _get_db_test
    return aplicacion


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # raise_server_exceptions=False: los errores 500 se ven como respuestas reales.
    with TestClient(app, raise_server_exceptions=False) as cliente:
        yield cliente
