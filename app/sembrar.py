"""Escritura del contenido en Postgres (idempotente y transaccional).

El contenido se calcula antes (`app.contenido`); aquí solo se hace el upsert dentro de una única
transacción. Lo que ya no existe en `contenido/` se borra (ejercicios, lecciones, módulos y
datasets, en ese orden por las claves foráneas).
"""

from typing import Any

from sqlalchemy import Engine, delete, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.contenido import ContenidoConstruido
from app.models import Dataset, Ejercicio, Leccion, Modulo


def _upsert(db: Session, modelo: Any, filas: list[dict[str, Any]], clave: list[str]) -> None:
    if not filas:
        return
    sentencia = insert(modelo).values(filas)
    actualizables = {
        c.name: sentencia.excluded[c.name] for c in modelo.__table__.columns if c.name not in clave
    }
    db.execute(sentencia.on_conflict_do_update(index_elements=clave, set_=actualizables))


def aplicar(db: Session, datos: ContenidoConstruido) -> None:
    """Sincroniza la base con `datos`. El llamador es dueño de la transacción (commit/rollback)."""
    # Los `orden` son UNIQUE: se invierte el signo de los existentes para poder reordenar
    # (por ejemplo intercambiar dos lecciones) sin choques temporales; el upsert los repone.
    db.execute(update(Modulo).values(orden=-Modulo.orden))
    db.execute(update(Leccion).values(orden=-Leccion.orden))
    db.execute(update(Ejercicio).values(orden=-Ejercicio.orden))

    ids_ejercicios = [e["id"] for e in datos.ejercicios]
    slugs_lecciones = [x["slug"] for x in datos.lecciones]
    slugs_modulos = [m["slug"] for m in datos.modulos]
    slugs_datasets = [d["slug"] for d in datos.datasets]

    # Primero lo que depende de otras tablas (ejercicios -> lecciones -> módulos y datasets).
    db.execute(delete(Ejercicio).where(Ejercicio.id.not_in(ids_ejercicios)))
    db.execute(delete(Leccion).where(Leccion.slug.not_in(slugs_lecciones)))

    _upsert(db, Modulo, datos.modulos, ["slug"])
    _upsert(db, Dataset, datos.datasets, ["slug"])
    _upsert(db, Leccion, datos.lecciones, ["slug"])
    _upsert(db, Ejercicio, datos.ejercicios, ["id"])

    db.execute(delete(Modulo).where(Modulo.slug.not_in(slugs_modulos)))
    db.execute(delete(Dataset).where(Dataset.slug.not_in(slugs_datasets)))


def sembrar(engine: Engine, datos: ContenidoConstruido) -> None:
    """Aplica `datos` en una sola transacción: si algo falla no se escribe nada."""
    with Session(engine) as db, db.begin():
        aplicar(db, datos)
