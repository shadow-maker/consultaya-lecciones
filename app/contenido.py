"""Carga, validación y construcción del contenido (`contenido/`) para el seed.

Flujo (ver `docs/04-contenido.md`):

1. `cargar(dir)` lee los YAML/SQL y valida su estructura y sus referencias cruzadas.
2. `construir(contenido)` crea cada dataset como SQLite en memoria, ejecuta ejemplos y soluciones
   y devuelve las filas listas para insertar en Postgres.

Nada de aquí toca Postgres: así, cualquier error aborta el seed antes de escribir nada.
"""

import hashlib
import math
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

RAIZ_CONTENIDO = Path(__file__).resolve().parent.parent / "contenido"
PATRON_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MUESTRA_FILAS = 5


class ContenidoError(Exception):
    """Error en el contenido, con un mensaje claro (archivo, lección, ejercicio…)."""


# --- Esquemas del contenido (lo que se lee de los YAML) -----------------------------------------


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModuloYaml(_Modelo):
    slug: str = Field(max_length=40)
    nombre: str = Field(max_length=60)
    orden: int
    descripcion: str


class ColumnaYaml(_Modelo):
    nombre: str
    tipo: str


class TablaYaml(_Modelo):
    nombre: str
    descripcion: str
    columnas: list[ColumnaYaml] = Field(min_length=1)


class DatasetYaml(_Modelo):
    slug: str = Field(max_length=40)
    nombre: str = Field(max_length=120)
    lugar: str = Field(max_length=120)
    icono: str = Field(max_length=40)
    descripcion: str
    tablas: list[TablaYaml] = Field(min_length=1)


class EjemploYaml(_Modelo):
    sql: str
    nota: str | None = None


class SeccionYaml(_Modelo):
    titulo: str
    cuerpo_md: str
    ejemplo: EjemploYaml | None = None
    tip: str | None = None


class EjercicioYaml(_Modelo):
    enunciado_md: str
    solucion_sql: str
    ordenado: bool = False


class LeccionYaml(_Modelo):
    slug: str = Field(max_length=60)
    modulo: str
    orden: int
    dataset: str
    duracion_min: int = Field(gt=0)
    titulo: str = Field(max_length=160)
    resumen: str
    tags: list[str] = []
    aprenderas: list[str] = []
    secciones: list[SeccionYaml] = Field(min_length=1)
    ejercicios: list[EjercicioYaml] = Field(min_length=1)


@dataclass
class Contenido:
    """Contenido ya leído y validado. Cada dataset trae su script SQL."""

    modulos: list[ModuloYaml]
    datasets: list[tuple[DatasetYaml, str]]
    lecciones: list[LeccionYaml]


@dataclass
class ContenidoConstruido:
    """Filas listas para insertar (diccionarios con los nombres de columna de cada tabla)."""

    modulos: list[dict[str, Any]]
    datasets: list[dict[str, Any]]
    lecciones: list[dict[str, Any]]
    ejercicios: list[dict[str, Any]]

    def resumen(self) -> str:
        return (
            f"{len(self.modulos)} módulos · {len(self.datasets)} datasets · "
            f"{len(self.lecciones)} lecciones · {len(self.ejercicios)} ejercicios"
        )


# --- Lectura y validación ------------------------------------------------------------------------


def _leer_yaml(ruta: Path, raiz: Path) -> Any:
    try:
        return yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContenidoError(f"{ruta.relative_to(raiz)}: no se pudo leer el YAML ({exc}).") from exc


def _validar[T: BaseModel](modelo: type[T], datos: Any, ruta: Path, raiz: Path) -> T:
    try:
        return modelo.model_validate(datos)
    except ValidationError as exc:
        detalle = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or '(raíz)'}: {e['msg']}" for e in exc.errors()
        )
        raise ContenidoError(f"{ruta.relative_to(raiz)}: {detalle}") from exc


def _slugs_unicos(items: list[Any], que: str) -> None:
    vistos: set[str] = set()
    for item in items:
        if not PATRON_SLUG.match(item.slug):
            raise ContenidoError(
                f"{que} '{item.slug}': el slug debe ser minúsculas, números y guiones."
            )
        if item.slug in vistos:
            raise ContenidoError(f"{que} '{item.slug}': slug repetido.")
        vistos.add(item.slug)


def _ordenes_unicos(items: list[Any], que: str) -> None:
    vistos: dict[int, str] = {}
    for item in items:
        if item.orden in vistos:
            raise ContenidoError(
                f"{que} '{item.slug}' y '{vistos[item.orden]}' repiten el orden {item.orden}."
            )
        vistos[item.orden] = item.slug


def cargar(raiz: Path = RAIZ_CONTENIDO) -> Contenido:
    """Lee `contenido/` y valida estructura, slugs, órdenes y referencias."""
    ruta_modulos = raiz / "modulos.yaml"
    if not ruta_modulos.is_file():
        raise ContenidoError(f"No existe {ruta_modulos}.")
    datos_modulos = _leer_yaml(ruta_modulos, raiz)
    if not isinstance(datos_modulos, list):
        raise ContenidoError("modulos.yaml: debe ser una lista de módulos.")
    modulos = [_validar(ModuloYaml, d, ruta_modulos, raiz) for d in datos_modulos]

    datasets: list[tuple[DatasetYaml, str]] = []
    for ruta in sorted((raiz / "datasets").glob("*.yaml")):
        ds = _validar(DatasetYaml, _leer_yaml(ruta, raiz), ruta, raiz)
        ruta_sql = ruta.with_suffix(".sql")
        if not ruta_sql.is_file():
            raise ContenidoError(f"{ruta.relative_to(raiz)}: falta el archivo {ruta_sql.name}.")
        datasets.append((ds, ruta_sql.read_text(encoding="utf-8")))

    lecciones = [
        _validar(LeccionYaml, _leer_yaml(ruta, raiz), ruta, raiz)
        for ruta in sorted((raiz / "lecciones").glob("*.yaml"))
    ]

    _slugs_unicos(modulos, "Módulo")
    _ordenes_unicos(modulos, "Módulo")
    _slugs_unicos([d for d, _ in datasets], "Dataset")
    _slugs_unicos(lecciones, "Lección")
    _ordenes_unicos(lecciones, "Lección")

    slugs_modulos = {m.slug for m in modulos}
    slugs_datasets = {d.slug for d, _ in datasets}
    for lec in lecciones:
        if lec.modulo not in slugs_modulos:
            raise ContenidoError(f"Lección '{lec.slug}': el módulo '{lec.modulo}' no existe.")
        if lec.dataset not in slugs_datasets:
            raise ContenidoError(f"Lección '{lec.slug}': el dataset '{lec.dataset}' no existe.")
        if not any(s.ejemplo for s in lec.secciones):
            raise ContenidoError(
                f"Lección '{lec.slug}': necesita al menos una sección con ejemplo."
            )
    return Contenido(modulos=modulos, datasets=datasets, lecciones=lecciones)


# --- Ejecución con SQLite ------------------------------------------------------------------------


def _json_valido(valor: Any) -> bool:
    if valor is None or isinstance(valor, int | str):
        return True
    return isinstance(valor, float) and math.isfinite(valor)


def ejecutar(conn: sqlite3.Connection, sql: str) -> dict[str, Any]:
    """Ejecuta una consulta y devuelve un `ResultadoSQL`: columnas y filas."""
    cursor = conn.execute(sql)
    if cursor.description is None:
        raise ContenidoError("la consulta no devuelve filas (¿es un SELECT?)")
    filas = [list(fila) for fila in cursor.fetchall()]
    if not all(_json_valido(v) for fila in filas for v in fila):
        raise ContenidoError("el resultado contiene valores que no se pueden guardar como JSON")
    return {"columnas": [d[0] for d in cursor.description], "filas": filas}


def _construir_dataset(ds: DatasetYaml, script: str) -> tuple[sqlite3.Connection, dict[str, Any]]:
    """Crea la base SQLite en memoria del dataset y devuelve (conexión, fila de `datasets`)."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(script)
    except sqlite3.Error as exc:
        conn.close()
        raise ContenidoError(
            f"Dataset '{ds.slug}': error al ejecutar {ds.slug}.sql ({exc})."
        ) from exc

    reales = {
        nombre: [fila[1] for fila in conn.execute(f'PRAGMA table_info("{nombre}")')]
        for (nombre,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    declaradas = [t.nombre for t in ds.tablas]
    if sorted(declaradas) != sorted(reales):
        conn.close()
        raise ContenidoError(
            f"Dataset '{ds.slug}': las tablas del YAML {sorted(declaradas)} no coinciden con "
            f"las del .sql {sorted(reales)}."
        )

    tablas: list[dict[str, Any]] = []
    for t in ds.tablas:
        nombres = [c.nombre for c in t.columnas]
        if nombres != reales[t.nombre]:
            conn.close()
            raise ContenidoError(
                f"Dataset '{ds.slug}', tabla '{t.nombre}': las columnas del YAML {nombres} no "
                f"coinciden con las del .sql {reales[t.nombre]}."
            )
        total = conn.execute(f'SELECT COUNT(*) FROM "{t.nombre}"').fetchone()[0]
        tablas.append(
            {
                "nombre": t.nombre,
                "descripcion": t.descripcion,
                "filas_total": total,
                "columnas": [{"nombre": c.nombre, "tipo": c.tipo} for c in t.columnas],
                "muestra": ejecutar(conn, f'SELECT * FROM "{t.nombre}" LIMIT {MUESTRA_FILAS}'),
            }
        )

    archivo = conn.serialize()
    fila = {
        "slug": ds.slug,
        "nombre": ds.nombre,
        "lugar": ds.lugar,
        "descripcion": ds.descripcion,
        "icono": ds.icono,
        "tablas": tablas,
        "archivo": archivo,
        "archivo_sha256": hashlib.sha256(archivo).hexdigest(),
    }
    # Los ejemplos y soluciones son consultas de lectura: se evita cualquier escritura accidental.
    conn.execute("PRAGMA query_only = ON")
    return conn, fila


def construir(contenido: Contenido) -> ContenidoConstruido:
    """Ejecuta todo el contenido con SQLite y devuelve las filas a insertar. No toca Postgres."""
    modulos = [m.model_dump() for m in contenido.modulos]
    conexiones: dict[str, sqlite3.Connection] = {}
    datasets: list[dict[str, Any]] = []
    lecciones: list[dict[str, Any]] = []
    ejercicios: list[dict[str, Any]] = []
    try:
        for ds, script in contenido.datasets:
            conexiones[ds.slug], fila = _construir_dataset(ds, script)
            datasets.append(fila)

        for lec in sorted(contenido.lecciones, key=lambda x: x.orden):
            conn = conexiones[lec.dataset]
            secciones: list[dict[str, Any]] = []
            for n, sec in enumerate(lec.secciones, start=1):
                ejemplo = None
                if sec.ejemplo:
                    try:
                        resultado = ejecutar(conn, sec.ejemplo.sql)
                    except (sqlite3.Error, ContenidoError) as exc:
                        raise ContenidoError(
                            f"Lección '{lec.slug}', sección {n} ('{sec.titulo}'): error en el "
                            f"ejemplo ({exc})."
                        ) from exc
                    ejemplo = {
                        "sql": sec.ejemplo.sql,
                        "nota": sec.ejemplo.nota,
                        "resultado": resultado,
                    }
                secciones.append(
                    {
                        "orden": n,
                        "titulo": sec.titulo,
                        "cuerpo_md": sec.cuerpo_md,
                        "ejemplo": ejemplo,
                        "tip": sec.tip,
                    }
                )
            lecciones.append(
                {
                    "slug": lec.slug,
                    "modulo_slug": lec.modulo,
                    "orden": lec.orden,
                    "titulo": lec.titulo,
                    "resumen": lec.resumen,
                    "duracion_min": lec.duracion_min,
                    "dataset_slug": lec.dataset,
                    "tags": lec.tags,
                    "aprenderas": lec.aprenderas,
                    "secciones": secciones,
                }
            )
            for n, ej in enumerate(lec.ejercicios, start=1):
                try:
                    esperado = ejecutar(conn, ej.solucion_sql)
                except (sqlite3.Error, ContenidoError) as exc:
                    raise ContenidoError(
                        f"Lección '{lec.slug}', ejercicio {n}: error en la solución ({exc})."
                    ) from exc
                ejercicios.append(
                    {
                        "id": f"{lec.slug}-{n}",
                        "leccion_slug": lec.slug,
                        "orden": n,
                        "enunciado_md": ej.enunciado_md,
                        "solucion_sql": ej.solucion_sql,
                        "ordenado": ej.ordenado,
                        "resultado_esperado": esperado,
                    }
                )
    finally:
        for conn in conexiones.values():
            conn.close()
    return ContenidoConstruido(modulos, datasets, lecciones, ejercicios)


def cargar_y_construir(raiz: Path = RAIZ_CONTENIDO) -> ContenidoConstruido:
    return construir(cargar(raiz))
