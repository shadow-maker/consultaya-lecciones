"""Seed: contenido real contra la tabla de resultados esperados de `docs/04-contenido.md`."""

import shutil
import sqlite3
from pathlib import Path

import pytest
import yaml
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app import sembrar as modulo_sembrar
from app.contenido import (
    RAIZ_CONTENIDO,
    ContenidoConstruido,
    ContenidoError,
    cargar,
    cargar_y_construir,
    construir,
)
from app.models import Dataset, Ejercicio, Leccion, Modulo
from app.sembrar import sembrar
from scripts import seed as script_seed

# id -> (filas, columnas, ordenado)
FORMAS = {
    "select-from-1": (12, 5, False),
    "select-from-2": (12, 2, False),
    "where-1": (3, 2, False),
    "where-2": (3, 2, False),
    "order-limit-1": (3, 2, True),
    "order-limit-2": (6, 1, True),
    "filtros-1": (8, 3, False),
    "filtros-2": (2, 2, False),
    "agregacion-1": (1, 1, False),
    "agregacion-2": (1, 1, False),
    "group-by-1": (5, 2, True),
    "group-by-2": (3, 2, False),
    "join-1": (15, 2, False),
    "join-2": (6, 2, False),
    "metricas-1": (8, 2, True),
    "metricas-2": (3, 2, False),
}


def _ejercicio(datos: ContenidoConstruido, ejercicio_id: str) -> dict:
    return next(e for e in datos.ejercicios if e["id"] == ejercicio_id)


def _filas(datos: ContenidoConstruido, ejercicio_id: str) -> list[list]:
    return _ejercicio(datos, ejercicio_id)["resultado_esperado"]["filas"]


def _copiar_contenido(destino: Path) -> Path:
    raiz = destino / "contenido"
    shutil.copytree(RAIZ_CONTENIDO, raiz)
    return raiz


def _editar_yaml(ruta: Path, cambiar) -> None:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    cambiar(datos)
    ruta.write_text(yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _conteos(db: Session) -> tuple[int, int, int, int]:
    return tuple(  # type: ignore[return-value]
        db.scalar(select(func.count()).select_from(m))
        for m in (Modulo, Dataset, Leccion, Ejercicio)
    )


# --- Contenido real --------------------------------------------------------------------------


def test_resumen_del_contenido(datos_contenido: ContenidoConstruido) -> None:
    assert datos_contenido.resumen() == "3 módulos · 3 datasets · 8 lecciones · 16 ejercicios"


def test_ejercicios_por_modulo(datos_contenido: ContenidoConstruido) -> None:
    modulo_de = {x["slug"]: x["modulo_slug"] for x in datos_contenido.lecciones}
    por_modulo: dict[str, int] = {}
    for e in datos_contenido.ejercicios:
        m = modulo_de[e["leccion_slug"]]
        por_modulo[m] = por_modulo.get(m, 0) + 1
    assert por_modulo == {"basico": 6, "intermedio": 6, "avanzado": 4}


def test_ids_y_orden_de_ejercicios(datos_contenido: ContenidoConstruido) -> None:
    assert sorted(e["id"] for e in datos_contenido.ejercicios) == sorted(FORMAS)
    for e in datos_contenido.ejercicios:
        assert e["id"] == f"{e['leccion_slug']}-{e['orden']}"
    assert [x["slug"] for x in datos_contenido.lecciones] == [
        "select-from",
        "where",
        "order-limit",
        "filtros",
        "agregacion",
        "group-by",
        "join",
        "metricas",
    ]
    assert [x["orden"] for x in datos_contenido.lecciones] == list(range(1, 9))


@pytest.mark.parametrize("ejercicio_id", sorted(FORMAS))
def test_forma_del_resultado_esperado(
    datos_contenido: ContenidoConstruido, ejercicio_id: str
) -> None:
    filas, columnas, ordenado = FORMAS[ejercicio_id]
    ejercicio = _ejercicio(datos_contenido, ejercicio_id)
    resultado = ejercicio["resultado_esperado"]
    assert len(resultado["filas"]) == filas
    assert len(resultado["columnas"]) == columnas
    assert all(len(f) == columnas for f in resultado["filas"])
    assert ejercicio["ordenado"] is ordenado


def test_valores_del_resultado_esperado(datos_contenido: ContenidoConstruido) -> None:
    f = lambda i: _filas(datos_contenido, i)  # noqa: E731

    assert f("where-1") == [
        ["Inca Kola 500 ml", 3.5],
        ["Coca-Cola 1.5 L", 7.0],
        ["Agua San Luis 625 ml", 2.0],
    ]
    assert f("where-2") == [
        ["Aceite Primor 1 L", 18],
        ["Yogurt Laive 1 L", 15],
        ["Detergente Bolívar 500 g", 12],
    ]
    assert f("order-limit-1") == [
        ["Aceite Primor 1 L", 11.5],
        ["Detergente Bolívar 500 g", 8.9],
        ["Coca-Cola 1.5 L", 7.0],
    ]
    nombres = [fila[0] for fila in f("order-limit-2")]
    assert nombres[0] == "Carlos Rojas" and nombres[-1] == "Rosa Mamani"
    assert nombres == sorted(nombres)
    assert [fila[0] for fila in f("filtros-1")] == [2, 3, 6, 7, 9, 12, 13, 16]
    assert [fila[0] for fila in f("filtros-2")] == [
        "Cevichería La Chalaca",
        "Sanguchería Don Lucho",
    ]
    assert f("agregacion-1") == [[12]]
    assert f("agregacion-2")[0][0] == pytest.approx(708.40)

    por_distrito = {fila[0]: fila[1] for fila in f("group-by-1")}
    assert por_distrito == pytest.approx(
        {"Miraflores": 275.4, "Lince": 161.7, "San Isidro": 137.5, "Surco": 103.9, "Barranco": 29.9}
    )
    assert [fila[0] for fila in f("group-by-1")] == [
        "Miraflores",
        "Lince",
        "San Isidro",
        "Surco",
        "Barranco",
    ]
    assert {tuple(fila) for fila in f("group-by-2")} == {
        ("Lince", 4),
        ("Miraflores", 4),
        ("Surco", 3),
    }
    assert dict(map(tuple, f("join-2"))) == {
        "Bebidas": 12,
        "Panadería": 18,
        "Lácteos": 6,
        "Abarrotes": 4,
        "Snacks": 6,
        "Limpieza": 1,
    }
    tasas = f("metricas-1")
    assert tasas[0][0] == "Remarketing" and tasas[0][1] == 6.0
    assert tasas[-1][0] == "Regreso a clases" and tasas[-1][1] == 2.0
    assert dict(map(tuple, f("metricas-2"))) == {
        "Facebook": 3300,
        "Instagram": 3000,
        "Google Ads": 4300,
    }


def test_ejemplos_tienen_resultado(datos_contenido: ContenidoConstruido) -> None:
    for lec in datos_contenido.lecciones:
        con_ejemplo = [s for s in lec["secciones"] if s["ejemplo"]]
        assert con_ejemplo, lec["slug"]
        for s in con_ejemplo:
            assert s["ejemplo"]["resultado"]["columnas"], lec["slug"]
        assert [s["orden"] for s in lec["secciones"]] == list(range(1, len(lec["secciones"]) + 1))


def test_datasets_archivo_y_tablas(datos_contenido: ContenidoConstruido) -> None:
    import hashlib

    esperadas = {
        "bodega": {"productos": 12, "clientes": 6, "ventas": 15},
        "delivery": {"restaurantes": 5, "pedidos": 16},
        "campanas": {"campanas": 8},
    }
    assert {d["slug"] for d in datos_contenido.datasets} == set(esperadas)
    for ds in datos_contenido.datasets:
        assert hashlib.sha256(ds["archivo"]).hexdigest() == ds["archivo_sha256"]
        conn = sqlite3.connect(":memory:")
        conn.deserialize(ds["archivo"])
        for tabla in ds["tablas"]:
            assert tabla["filas_total"] == esperadas[ds["slug"]][tabla["nombre"]]
            real = conn.execute(f"SELECT COUNT(*) FROM {tabla['nombre']}").fetchone()[0]
            assert real == tabla["filas_total"]
            assert len(tabla["muestra"]["filas"]) == min(5, tabla["filas_total"])
            assert tabla["muestra"]["columnas"] == [c["nombre"] for c in tabla["columnas"]]
        conn.close()


def test_el_contenido_no_usa_tipos_ni_tildes_en_el_sql() -> None:
    for sql in RAIZ_CONTENIDO.glob("datasets/*.sql"):
        encabezados = [
            ln for ln in sql.read_text(encoding="utf-8").splitlines() if ln.startswith("CREATE")
        ]
        assert encabezados and all(ln.isascii() for ln in encabezados)
        assert not any(t in " ".join(encabezados) for t in ("DECIMAL", "DATE"))


# --- Escritura en Postgres -------------------------------------------------------------------


def test_sembrar_escribe_todo(motor: Engine, datos_contenido: ContenidoConstruido) -> None:
    sembrar(motor, datos_contenido)
    with Session(motor) as db:
        assert _conteos(db) == (3, 3, 8, 16)
        bodega = db.get(Dataset, "bodega")
        assert bodega is not None and bytes(bodega.archivo)[:15] == b"SQLite format 3"
        where1 = db.get(Ejercicio, "where-1")
        assert where1 is not None and where1.solucion_sql.startswith("SELECT nombre, precio")


def test_sembrar_es_idempotente(motor: Engine, datos_contenido: ContenidoConstruido) -> None:
    sembrar(motor, datos_contenido)
    with Session(motor) as db:
        shas = dict(db.execute(select(Dataset.slug, Dataset.archivo_sha256)).all())
    sembrar(motor, cargar_y_construir())
    with Session(motor) as db:
        assert _conteos(db) == (3, 3, 8, 16)
        assert dict(db.execute(select(Dataset.slug, Dataset.archivo_sha256)).all()) == shas


def test_sembrar_actualiza_y_borra_lo_que_ya_no_existe(
    motor: Engine, datos_contenido: ContenidoConstruido
) -> None:
    sembrar(motor, datos_contenido)
    reducido = ContenidoConstruido(
        modulos=[m for m in datos_contenido.modulos if m["slug"] != "avanzado"],
        datasets=[d for d in datos_contenido.datasets if d["slug"] != "campanas"],
        lecciones=[x for x in datos_contenido.lecciones if x["slug"] in {"select-from", "where"}],
        ejercicios=[
            e for e in datos_contenido.ejercicios if e["leccion_slug"] in {"select-from", "where"}
        ],
    )
    reducido.modulos[0] = {**reducido.modulos[0], "nombre": "Básico (editado)"}
    sembrar(motor, reducido)
    with Session(motor) as db:
        assert _conteos(db) == (2, 2, 2, 4)
        assert db.get(Modulo, "basico").nombre == "Básico (editado)"  # type: ignore[union-attr]
        assert db.get(Leccion, "join") is None
        assert db.get(Ejercicio, "order-limit-1") is None


def test_sembrar_permite_reordenar_lecciones(
    motor: Engine, datos_contenido: ContenidoConstruido
) -> None:
    sembrar(motor, datos_contenido)
    lecciones = [dict(x) for x in datos_contenido.lecciones]
    lecciones[0]["orden"], lecciones[1]["orden"] = lecciones[1]["orden"], lecciones[0]["orden"]
    sembrar(
        motor,
        ContenidoConstruido(
            datos_contenido.modulos, datos_contenido.datasets, lecciones, datos_contenido.ejercicios
        ),
    )
    with Session(motor) as db:
        assert db.get(Leccion, "select-from").orden == 2  # type: ignore[union-attr]
        assert db.get(Leccion, "where").orden == 1  # type: ignore[union-attr]


def test_sembrar_es_transaccional(
    motor: Engine, datos_contenido: ContenidoConstruido, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = modulo_sembrar._upsert

    def falla_en_ejercicios(db, modelo, filas, clave):  # type: ignore[no-untyped-def]
        if modelo is Ejercicio:
            raise RuntimeError("fallo simulado a mitad del seed")
        original(db, modelo, filas, clave)

    monkeypatch.setattr(modulo_sembrar, "_upsert", falla_en_ejercicios)
    with pytest.raises(RuntimeError):
        sembrar(motor, datos_contenido)
    with Session(motor) as db:
        assert _conteos(db) == (0, 0, 0, 0)


# --- Validaciones y errores ------------------------------------------------------------------


def test_solucion_con_error_aborta_con_mensaje_claro(tmp_path: Path) -> None:
    raiz = _copiar_contenido(tmp_path)
    _editar_yaml(
        raiz / "lecciones" / "02-where.yaml",
        lambda d: d["ejercicios"][1].update(solucion_sql="SELECT nombre FROM tabla_inexistente"),
    )
    with pytest.raises(ContenidoError) as exc:
        cargar_y_construir(raiz)
    mensaje = str(exc.value)
    assert "where" in mensaje and "ejercicio 2" in mensaje and "tabla_inexistente" in mensaje


def test_ejemplo_con_error_aborta_con_mensaje_claro(tmp_path: Path) -> None:
    raiz = _copiar_contenido(tmp_path)
    _editar_yaml(
        raiz / "lecciones" / "01-select-from.yaml",
        lambda d: d["secciones"][1]["ejemplo"].update(sql="SELEC nombre FROM clientes"),
    )
    with pytest.raises(ContenidoError) as exc:
        cargar_y_construir(raiz)
    assert "select-from" in str(exc.value) and "sección 2" in str(exc.value)


def test_script_con_error_no_escribe_nada(
    tmp_path: Path, motor: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    raiz = _copiar_contenido(tmp_path)
    _editar_yaml(
        raiz / "lecciones" / "08-metricas.yaml",
        lambda d: d["ejercicios"][0].update(solucion_sql="SELECT * FROM nada"),
    )
    assert script_seed.main(["--contenido", str(raiz)]) == 1
    assert "metricas" in capsys.readouterr().err
    with Session(motor) as db:
        assert _conteos(db) == (0, 0, 0, 0)


def test_script_siembra_y_muestra_resumen(
    motor: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    assert script_seed.main([]) == 0
    assert capsys.readouterr().out.strip() == "3 módulos · 3 datasets · 8 lecciones · 16 ejercicios"
    with Session(motor) as db:
        assert _conteos(db) == (3, 3, 8, 16)


@pytest.mark.parametrize(
    ("cambio", "texto"),
    [
        ("lecciones/02-where.yaml|slug=select-from", "slug repetido"),
        ("lecciones/02-where.yaml|orden=1", "repiten el orden"),
        ("lecciones/02-where.yaml|slug=Mal Slug", "slug debe ser"),
        ("lecciones/02-where.yaml|modulo=inexistente", "el módulo 'inexistente' no existe"),
        ("lecciones/02-where.yaml|dataset=inexistente", "el dataset 'inexistente' no existe"),
        ("lecciones/02-where.yaml|ejercicios=[]", "ejercicios"),
        ("lecciones/02-where.yaml|campo_raro=1", "campo_raro"),
        ("modulos.yaml|0:orden=2", "repiten el orden"),
    ],
)
def test_validaciones_de_contenido(tmp_path: Path, cambio: str, texto: str) -> None:
    raiz = _copiar_contenido(tmp_path)
    archivo, asignacion = cambio.split("|")
    clave, valor = asignacion.split("=", 1)

    def cambiar(datos):  # type: ignore[no-untyped-def]
        if archivo == "modulos.yaml":
            indice, clave_real = clave.split(":")
            datos[int(indice)][clave_real] = int(valor)
        elif valor == "[]":
            datos[clave] = []
        elif clave == "orden":
            datos[clave] = int(valor)
        else:
            datos[clave] = valor

    _editar_yaml(raiz / archivo, cambiar)
    with pytest.raises(ContenidoError, match=texto):
        cargar(raiz)


def test_leccion_sin_ejemplos_falla(tmp_path: Path) -> None:
    raiz = _copiar_contenido(tmp_path)

    def sin_ejemplos(datos):  # type: ignore[no-untyped-def]
        for s in datos["secciones"]:
            s["ejemplo"] = None

    _editar_yaml(raiz / "lecciones" / "02-where.yaml", sin_ejemplos)
    with pytest.raises(ContenidoError, match="al menos una sección con ejemplo"):
        cargar(raiz)


def test_columnas_del_yaml_deben_coincidir_con_el_sql(tmp_path: Path) -> None:
    raiz = _copiar_contenido(tmp_path)
    _editar_yaml(
        raiz / "datasets" / "bodega.yaml",
        lambda d: d["tablas"][1]["columnas"].__setitem__(2, {"nombre": "ciudad", "tipo": "TEXT"}),
    )
    with pytest.raises(ContenidoError, match="columnas del YAML"):
        construir(cargar(raiz))


def test_tablas_del_yaml_deben_coincidir_con_el_sql(tmp_path: Path) -> None:
    raiz = _copiar_contenido(tmp_path)
    _editar_yaml(raiz / "datasets" / "bodega.yaml", lambda d: d["tablas"].pop())
    with pytest.raises(ContenidoError, match="tablas del YAML"):
        construir(cargar(raiz))


def test_sql_del_dataset_invalido(tmp_path: Path) -> None:
    raiz = _copiar_contenido(tmp_path)
    (raiz / "datasets" / "bodega.sql").write_text("CREATE TABLE x (", encoding="utf-8")
    with pytest.raises(ContenidoError, match="bodega.sql"):
        construir(cargar(raiz))


def test_dataset_sin_sql(tmp_path: Path) -> None:
    raiz = _copiar_contenido(tmp_path)
    (raiz / "datasets" / "delivery.sql").unlink()
    with pytest.raises(ContenidoError, match="falta el archivo delivery.sql"):
        cargar(raiz)


def test_las_consultas_no_pueden_escribir(tmp_path: Path) -> None:
    raiz = _copiar_contenido(tmp_path)
    _editar_yaml(
        raiz / "lecciones" / "02-where.yaml",
        lambda d: d["ejercicios"][0].update(solucion_sql="DELETE FROM productos"),
    )
    with pytest.raises(ContenidoError, match="ejercicio 1"):
        cargar_y_construir(raiz)
