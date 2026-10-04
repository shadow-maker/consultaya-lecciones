"""Engine y sesión de SQLAlchemy 2 (síncronos, psycopg 3)."""

from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

# Nombres estables para constraints (migraciones Alembic predecibles).
convencion_nombres = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convencion_nombres)


# `create_engine` no abre conexiones hasta el primer uso.
engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición."""
    with SessionLocal() as db:
        yield db
