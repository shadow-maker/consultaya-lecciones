"""Endpoints de lectura de contenido (públicos) y `/interno/estructura` (red interna).

Los `GET /api/lecciones/*` no exigen JWT: si llega uno (válido o no) simplemente se ignora.
Ningún endpoint devuelve `solucion_sql`: los schemas de respuesta no tienen ese campo y las
consultas ni siquiera la leen.
"""

import hashlib
import json
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import PREFIJO
from app.db import get_db
from app.errors import ApiError
from app.models import Dataset, Ejercicio, Leccion, Modulo
from app.schemas import (
    DatasetOut,
    EjercicioOut,
    EstructuraOut,
    LeccionOut,
    ModuloOut,
)

router = APIRouter(tags=["lecciones"])
router_interno = APIRouter(prefix="/interno", tags=["interno"], include_in_schema=False)

CACHE_ARCHIVO = "public, max-age=3600"
MEDIA_TYPE_SQLITE = "application/vnd.sqlite3"


def _ejercicios_por_leccion(db: Session) -> dict[str, list[tuple[str, int]]]:
    """`{leccion_slug: [(id, orden), ...]}` ordenado por `orden` (sin leer los resultados)."""
    filas = db.execute(
        select(Ejercicio.leccion_slug, Ejercicio.id, Ejercicio.orden).order_by(
            Ejercicio.leccion_slug, Ejercicio.orden
        )
    )
    por_leccion: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for leccion_slug, ejercicio_id, orden in filas:
        por_leccion[leccion_slug].append((ejercicio_id, orden))
    return por_leccion


@router.get("/modulos", summary="Módulos con sus lecciones y ejercicios")
def listar_modulos(db: Session = Depends(get_db)) -> list[ModuloOut]:
    ejercicios = _ejercicios_por_leccion(db)
    lecciones = db.execute(
        select(
            Leccion.slug,
            Leccion.modulo_slug,
            Leccion.orden,
            Leccion.titulo,
            Leccion.resumen,
            Leccion.duracion_min,
            Leccion.dataset_slug,
            Leccion.tags,
        ).order_by(Leccion.orden)
    )
    por_modulo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for lec in lecciones:
        por_modulo[lec.modulo_slug].append(
            {
                "slug": lec.slug,
                "orden": lec.orden,
                "titulo": lec.titulo,
                "resumen": lec.resumen,
                "duracion_min": lec.duracion_min,
                "dataset": lec.dataset_slug,
                "tags": lec.tags,
                "ejercicios": [{"id": i, "orden": o} for i, o in ejercicios[lec.slug]],
            }
        )
    modulos = db.scalars(select(Modulo).order_by(Modulo.orden))
    return [
        ModuloOut.model_validate(
            {
                "slug": m.slug,
                "nombre": m.nombre,
                "descripcion": m.descripcion,
                "orden": m.orden,
                "lecciones": por_modulo[m.slug],
            }
        )
        for m in modulos
    ]


@router.get("/lecciones/{slug}", summary="Detalle de una lección")
def obtener_leccion(slug: str, db: Session = Depends(get_db)) -> LeccionOut:
    leccion = db.get(Leccion, slug)
    if leccion is None:
        raise ApiError(404, "LECCION_NO_EXISTE", "La lección que buscas no existe.")
    modulo = db.get(Modulo, leccion.modulo_slug)
    assert modulo is not None  # garantizado por la clave foránea
    ejercicios = _ejercicios_por_leccion(db)[slug]
    anterior = db.scalar(
        select(Leccion.slug)
        .where(Leccion.orden < leccion.orden)
        .order_by(Leccion.orden.desc())
        .limit(1)
    )
    siguiente = db.scalar(
        select(Leccion.slug).where(Leccion.orden > leccion.orden).order_by(Leccion.orden).limit(1)
    )
    return LeccionOut.model_validate(
        {
            "slug": leccion.slug,
            "orden": leccion.orden,
            "titulo": leccion.titulo,
            "resumen": leccion.resumen,
            "duracion_min": leccion.duracion_min,
            "modulo": {"slug": modulo.slug, "nombre": modulo.nombre},
            "dataset": leccion.dataset_slug,
            "tags": leccion.tags,
            "aprenderas": leccion.aprenderas,
            "secciones": leccion.secciones,
            "ejercicios": [{"id": i, "orden": o} for i, o in ejercicios],
            "anterior": anterior,
            "siguiente": siguiente,
        }
    )


@router.get("/ejercicios/{ejercicio_id}", summary="Ejercicio (sin la solución)")
def obtener_ejercicio(ejercicio_id: str, db: Session = Depends(get_db)) -> EjercicioOut:
    fila = db.execute(
        select(
            Ejercicio.id,
            Ejercicio.leccion_slug,
            Ejercicio.orden,
            Ejercicio.enunciado_md,
            Ejercicio.ordenado,
            Ejercicio.resultado_esperado,
            Leccion.dataset_slug,
        )
        .join(Leccion, Leccion.slug == Ejercicio.leccion_slug)
        .where(Ejercicio.id == ejercicio_id)
    ).first()
    if fila is None:
        raise ApiError(404, "EJERCICIO_NO_EXISTE", "El ejercicio que buscas no existe.")
    total = db.scalar(
        select(func.count())
        .select_from(Ejercicio)
        .where(Ejercicio.leccion_slug == fila.leccion_slug)
    )
    return EjercicioOut(
        id=fila.id,
        leccion_slug=fila.leccion_slug,
        orden=fila.orden,
        total_en_leccion=total or 0,
        enunciado_md=fila.enunciado_md,
        dataset=fila.dataset_slug,
        ordenado=fila.ordenado,
        resultado_esperado=fila.resultado_esperado,
    )


@router.get("/datasets/{slug}", summary="Metadatos y tablas de un dataset")
def obtener_dataset(slug: str, db: Session = Depends(get_db)) -> DatasetOut:
    fila = db.execute(
        select(
            Dataset.slug,
            Dataset.nombre,
            Dataset.lugar,
            Dataset.descripcion,
            Dataset.icono,
            Dataset.tablas,
            Dataset.archivo_sha256,
        ).where(Dataset.slug == slug)
    ).first()
    if fila is None:
        raise ApiError(404, "DATASET_NO_EXISTE", "El dataset que buscas no existe.")
    return DatasetOut(
        slug=fila.slug,
        nombre=fila.nombre,
        lugar=fila.lugar,
        descripcion=fila.descripcion,
        icono=fila.icono,
        archivo_url=f"{PREFIJO}/datasets/{fila.slug}/archivo",
        archivo_sha256=fila.archivo_sha256,
        tablas=fila.tablas,
    )


def _coincide_etag(if_none_match: str | None, etag: str) -> bool:
    """¿`If-None-Match` incluye este ETag? Acepta `*`, listas y la forma débil `W/"..."`."""
    if not if_none_match:
        return False
    for candidato in if_none_match.split(","):
        valor = candidato.strip().removeprefix("W/")
        if valor == "*" or valor == etag:
            return True
    return False


@router.get(
    "/datasets/{slug}/archivo",
    summary="Archivo .sqlite del dataset (ETag/304)",
    response_class=Response,
    responses={
        200: {"content": {MEDIA_TYPE_SQLITE: {}}, "description": "Bytes del archivo SQLite."},
        304: {"description": "Sin cambios (coincide `If-None-Match`)."},
    },
)
def descargar_archivo(
    slug: str,
    if_none_match: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Response:
    sha256 = db.scalar(select(Dataset.archivo_sha256).where(Dataset.slug == slug))
    if sha256 is None:
        raise ApiError(404, "DATASET_NO_EXISTE", "El dataset que buscas no existe.")
    cabeceras = {"ETag": f'"{sha256}"', "Cache-Control": CACHE_ARCHIVO}
    if _coincide_etag(if_none_match, cabeceras["ETag"]):
        return Response(status_code=304, headers=cabeceras)
    archivo = db.scalar(select(Dataset.archivo).where(Dataset.slug == slug))
    return Response(content=archivo, media_type=MEDIA_TYPE_SQLITE, headers=cabeceras)


@router_interno.get("/estructura", summary="Estructura de módulos, lecciones y ejercicios")
def estructura(db: Session = Depends(get_db)) -> EstructuraOut:
    """La consume `progreso` (red interna; nginx no la expone).

    `version` es el SHA-256 de la estructura serializada en JSON canónico (claves ordenadas, sin
    espacios, UTF-8): cambia solo si cambian módulos, lecciones o ejercicios.
    """
    ejercicios = _ejercicios_por_leccion(db)
    lecciones = db.execute(
        select(Leccion.slug, Leccion.modulo_slug, Leccion.orden).order_by(Leccion.orden)
    )
    por_modulo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for lec in lecciones:
        por_modulo[lec.modulo_slug].append(
            {
                "slug": lec.slug,
                "orden": lec.orden,
                "ejercicios": [i for i, _ in ejercicios[lec.slug]],
            }
        )
    modulos = [
        {"slug": m.slug, "nombre": m.nombre, "orden": m.orden, "lecciones": por_modulo[m.slug]}
        for m in db.scalars(select(Modulo).order_by(Modulo.orden))
    ]
    canonico = json.dumps(modulos, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    version = hashlib.sha256(canonico.encode("utf-8")).hexdigest()
    return EstructuraOut.model_validate({"version": version, "modulos": modulos})
