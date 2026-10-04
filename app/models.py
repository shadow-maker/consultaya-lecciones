"""Modelos ORM (ver `docs/02-contratos-api.md`, "Servicio lecciones").

Importar aquí cada modelo para que Alembic los vea (`Base.metadata`).
"""

from typing import Any

from sqlalchemy import ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Modulo(Base):
    __tablename__ = "modulos"

    slug: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(60))
    descripcion: Mapped[str] = mapped_column(Text)
    orden: Mapped[int] = mapped_column(Integer, unique=True)


class Dataset(Base):
    __tablename__ = "datasets"

    slug: Mapped[str] = mapped_column(String(40), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    lugar: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str] = mapped_column(Text)
    icono: Mapped[str] = mapped_column(String(40))
    tablas: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # lista de DatasetTabla
    archivo: Mapped[bytes] = mapped_column(LargeBinary)  # .sqlite generado por el seed
    archivo_sha256: Mapped[str] = mapped_column(String(64))


class Leccion(Base):
    __tablename__ = "lecciones"
    __table_args__ = (UniqueConstraint("orden"),)

    slug: Mapped[str] = mapped_column(String(60), primary_key=True)
    modulo_slug: Mapped[str] = mapped_column(String(40), ForeignKey("modulos.slug"))
    orden: Mapped[int] = mapped_column(Integer)  # orden global en la ruta (1..N)
    titulo: Mapped[str] = mapped_column(String(160))
    resumen: Mapped[str] = mapped_column(Text)
    duracion_min: Mapped[int] = mapped_column(Integer)
    dataset_slug: Mapped[str] = mapped_column(String(40), ForeignKey("datasets.slug"))
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]"), default=list
    )
    aprenderas: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]"), default=list
    )
    secciones: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # lista de Seccion


class Ejercicio(Base):
    __tablename__ = "ejercicios"
    __table_args__ = (UniqueConstraint("leccion_slug", "orden"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)  # '<leccion_slug>-<orden>'
    leccion_slug: Mapped[str] = mapped_column(String(60), ForeignKey("lecciones.slug"))
    orden: Mapped[int] = mapped_column(Integer)
    enunciado_md: Mapped[str] = mapped_column(Text)
    solucion_sql: Mapped[str] = mapped_column(Text)  # NUNCA se expone por la API
    ordenado: Mapped[bool] = mapped_column(server_default=text("false"), default=False)
    resultado_esperado: Mapped[dict[str, Any]] = mapped_column(JSONB)  # ResultadoSQL
