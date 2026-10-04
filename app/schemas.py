"""Schemas Pydantic (request/response)."""

from typing import Any

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


# --- Servicio lecciones (ver `docs/02-contratos-api.md`) ----------------------------------------


class ResultadoSQL(BaseModel):
    columnas: list[str]
    filas: list[list[Any]]


class EjemploOut(BaseModel):
    sql: str
    nota: str | None = None
    resultado: ResultadoSQL


class SeccionOut(BaseModel):
    orden: int
    titulo: str
    cuerpo_md: str
    ejemplo: EjemploOut | None = None
    tip: str | None = None


class EjercicioRefOut(BaseModel):
    id: str
    orden: int


class LeccionResumenOut(BaseModel):
    """Lección dentro de `GET /modulos`."""

    slug: str
    orden: int
    titulo: str
    resumen: str
    duracion_min: int
    dataset: str
    tags: list[str]
    ejercicios: list[EjercicioRefOut]


class ModuloOut(BaseModel):
    slug: str
    nombre: str
    descripcion: str
    orden: int
    lecciones: list[LeccionResumenOut]


class ModuloRefOut(BaseModel):
    slug: str
    nombre: str


class LeccionOut(BaseModel):
    slug: str
    orden: int
    titulo: str
    resumen: str
    duracion_min: int
    modulo: ModuloRefOut
    dataset: str
    tags: list[str]
    aprenderas: list[str]
    secciones: list[SeccionOut]
    ejercicios: list[EjercicioRefOut]
    anterior: str | None
    siguiente: str | None


class EjercicioOut(BaseModel):
    """Ejercicio para el estudiante. **No** incluye `solucion_sql`."""

    id: str
    leccion_slug: str
    orden: int
    total_en_leccion: int
    enunciado_md: str
    dataset: str
    ordenado: bool
    resultado_esperado: ResultadoSQL


class ColumnaOut(BaseModel):
    nombre: str
    tipo: str


class DatasetTablaOut(BaseModel):
    nombre: str
    descripcion: str
    filas_total: int
    columnas: list[ColumnaOut]
    muestra: ResultadoSQL


class DatasetOut(BaseModel):
    slug: str
    nombre: str
    lugar: str
    descripcion: str
    icono: str
    archivo_url: str
    archivo_sha256: str
    tablas: list[DatasetTablaOut]


class EstructuraLeccionOut(BaseModel):
    slug: str
    orden: int
    ejercicios: list[str]


class EstructuraModuloOut(BaseModel):
    slug: str
    nombre: str
    orden: int
    lecciones: list[EstructuraLeccionOut]


class EstructuraOut(BaseModel):
    version: str
    modulos: list[EstructuraModuloOut]
