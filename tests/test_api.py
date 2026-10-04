"""Endpoints de lecciones contra Postgres real (base `_test`) con el contenido real sembrado."""

import hashlib
import json
import sqlite3
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from app.auth import emitir_token
from app.contenido import ContenidoConstruido
from app.models import Ejercicio

P = "/api/lecciones"
SLUGS = [
    "select-from",
    "where",
    "order-limit",
    "filtros",
    "agregacion",
    "group-by",
    "join",
    "metricas",
]


def _todas_las_respuestas(client: TestClient, datos: ContenidoConstruido) -> list[str]:
    """Texto de todas las respuestas públicas (y la interna) sobre todo el contenido."""
    rutas = [f"{P}/modulos", "/interno/estructura"]
    rutas += [f"{P}/lecciones/{x['slug']}" for x in datos.lecciones]
    rutas += [f"{P}/ejercicios/{e['id']}" for e in datos.ejercicios]
    rutas += [f"{P}/datasets/{d['slug']}" for d in datos.datasets]
    textos = []
    for ruta in rutas:
        r = client.get(ruta)
        assert r.status_code == 200, ruta
        textos.append(r.text)
    return textos


# --- GET /modulos ----------------------------------------------------------------------------


def test_modulos_orden_y_forma(client: TestClient, sembrado: ContenidoConstruido) -> None:
    r = client.get(f"{P}/modulos")
    assert r.status_code == 200
    modulos = r.json()
    assert [m["slug"] for m in modulos] == ["basico", "intermedio", "avanzado"]
    assert [m["orden"] for m in modulos] == [1, 2, 3]
    assert modulos[0]["nombre"] == "Básico"
    assert [[x["slug"] for x in m["lecciones"]] for m in modulos] == [
        ["select-from", "where", "order-limit"],
        ["filtros", "agregacion", "group-by"],
        ["join", "metricas"],
    ]
    primera = modulos[0]["lecciones"][0]
    assert set(primera) == {
        "slug",
        "orden",
        "titulo",
        "resumen",
        "duracion_min",
        "dataset",
        "tags",
        "ejercicios",
    }
    assert primera["titulo"] == "Tu primera consulta: SELECT y FROM"
    assert primera["duracion_min"] == 10 and primera["dataset"] == "bodega"
    assert primera["ejercicios"] == [
        {"id": "select-from-1", "orden": 1},
        {"id": "select-from-2", "orden": 2},
    ]
    ordenes = [x["orden"] for m in modulos for x in m["lecciones"]]
    assert ordenes == list(range(1, 9))
    assert sum(len(x["ejercicios"]) for m in modulos for x in m["lecciones"]) == 16


def test_modulos_sin_contenido_devuelve_lista_vacia(client: TestClient) -> None:
    r = client.get(f"{P}/modulos")
    assert r.status_code == 200 and r.json() == []


# --- GET /lecciones/{slug} -------------------------------------------------------------------


def test_leccion_detalle(client: TestClient, sembrado: ContenidoConstruido) -> None:
    r = client.get(f"{P}/lecciones/where")
    assert r.status_code == 200
    d = r.json()
    assert set(d) == {
        "slug",
        "orden",
        "titulo",
        "resumen",
        "duracion_min",
        "modulo",
        "dataset",
        "tags",
        "aprenderas",
        "secciones",
        "ejercicios",
        "anterior",
        "siguiente",
    }
    assert d["slug"] == "where" and d["orden"] == 2 and d["duracion_min"] == 12
    assert d["modulo"] == {"slug": "basico", "nombre": "Básico"}
    assert d["dataset"] == "bodega"
    assert d["tags"] == ["where", "filtrar", "condicion", "comparar"]
    assert len(d["aprenderas"]) == 4
    assert d["ejercicios"] == [{"id": "where-1", "orden": 1}, {"id": "where-2", "orden": 2}]
    assert d["anterior"] == "select-from" and d["siguiente"] == "order-limit"

    s1, s2 = d["secciones"]
    assert s1["orden"] == 1 and s1["titulo"] == "La cláusula WHERE"
    assert s1["ejemplo"]["sql"].startswith("SELECT nombre, distrito")
    assert s1["ejemplo"]["nota"].startswith("Los textos van entre comillas")
    assert s1["ejemplo"]["resultado"]["columnas"] == ["nombre", "distrito"]
    assert len(s1["ejemplo"]["resultado"]["filas"]) == 3
    assert s1["tip"] is None
    assert "| Operador | Significa | Ejemplo |" in s2["cuerpo_md"]
    assert s2["ejemplo"]["nota"] is None


def test_leccion_sin_ejemplo_ni_tip(client: TestClient, sembrado: ContenidoConstruido) -> None:
    secciones = client.get(f"{P}/lecciones/select-from").json()["secciones"]
    assert secciones[0]["ejemplo"] is None and secciones[0]["tip"] is None
    assert secciones[2]["tip"].startswith("Las palabras clave")


def test_leccion_primera_y_ultima(client: TestClient, sembrado: ContenidoConstruido) -> None:
    primera = client.get(f"{P}/lecciones/select-from").json()
    assert primera["anterior"] is None and primera["siguiente"] == "where"
    ultima = client.get(f"{P}/lecciones/metricas").json()
    assert ultima["anterior"] == "join" and ultima["siguiente"] is None


def test_encadenado_anterior_siguiente(client: TestClient, sembrado: ContenidoConstruido) -> None:
    actual, recorrido = "select-from", []
    while actual:
        recorrido.append(actual)
        actual = client.get(f"{P}/lecciones/{actual}").json()["siguiente"]
    assert recorrido == SLUGS


def test_leccion_no_existe(client: TestClient, sembrado: ContenidoConstruido) -> None:
    r = client.get(f"{P}/lecciones/no-existe")
    assert r.status_code == 404
    assert r.json()["error"]["codigo"] == "LECCION_NO_EXISTE"
    assert r.json()["error"]["campos"] is None


# --- GET /ejercicios/{id} --------------------------------------------------------------------


def test_ejercicio_detalle(client: TestClient, sembrado: ContenidoConstruido) -> None:
    r = client.get(f"{P}/ejercicios/where-1")
    assert r.status_code == 200
    d = r.json()
    assert d == {
        "id": "where-1",
        "leccion_slug": "where",
        "orden": 1,
        "total_en_leccion": 2,
        "enunciado_md": (
            "Muestra el **nombre** y el **precio** de los productos de la categoría **Bebidas**."
        ),
        "dataset": "bodega",
        "ordenado": False,
        "resultado_esperado": {
            "columnas": ["nombre", "precio"],
            "filas": [
                ["Inca Kola 500 ml", 3.5],
                ["Coca-Cola 1.5 L", 7.0],
                ["Agua San Luis 625 ml", 2.0],
            ],
        },
    }


def test_ejercicio_ordenado_y_dataset_de_la_leccion(
    client: TestClient, sembrado: ContenidoConstruido
) -> None:
    d = client.get(f"{P}/ejercicios/group-by-1").json()
    assert d["ordenado"] is True and d["dataset"] == "delivery" and d["total_en_leccion"] == 2


def test_enteros_y_decimales_conservan_su_tipo(
    client: TestClient, sembrado: ContenidoConstruido
) -> None:
    filas = client.get(f"{P}/ejercicios/where-2").json()["resultado_esperado"]["filas"]
    assert filas[0][1] == 18 and isinstance(filas[0][1], int)
    # Los decimales con parte entera cero se serializan como 7.0, no como 7.
    assert '["Coca-Cola 1.5 L",7.0]' in client.get(f"{P}/ejercicios/where-1").text.replace(
        ", ", ","
    )


def test_ejercicio_no_existe(client: TestClient, sembrado: ContenidoConstruido) -> None:
    r = client.get(f"{P}/ejercicios/where-99")
    assert r.status_code == 404
    assert r.json()["error"]["codigo"] == "EJERCICIO_NO_EXISTE"


# --- La solución nunca sale por la API -------------------------------------------------------


def test_la_api_nunca_expone_solucion_sql(
    client: TestClient, sembrado: ContenidoConstruido
) -> None:
    textos = _todas_las_respuestas(client, sembrado)
    for texto in textos:
        assert "solucion" not in texto.lower()
    # Tampoco aparece el SQL de ninguna solución, ni siquiera dentro de otro campo.
    for ejercicio in sembrado.ejercicios:
        for texto in textos:
            assert ejercicio["solucion_sql"] not in texto, ejercicio["id"]


def test_el_openapi_no_declara_solucion_sql(client: TestClient) -> None:
    esquemas = client.get(f"{P}/openapi.json").json()["components"]["schemas"]
    propiedades = {p for e in esquemas.values() for p in e.get("properties", {})}
    assert (
        "solucion_sql" not in propiedades and propiedades
    )  # hay propiedades y ninguna es la solución


# --- Datasets --------------------------------------------------------------------------------


def test_dataset_detalle(client: TestClient, sembrado: ContenidoConstruido) -> None:
    r = client.get(f"{P}/datasets/bodega")
    assert r.status_code == 200
    d = r.json()
    assert set(d) == {
        "slug",
        "nombre",
        "lugar",
        "descripcion",
        "icono",
        "archivo_url",
        "archivo_sha256",
        "tablas",
    }
    assert d["nombre"] == "Bodega Doña Rosa" and d["lugar"] == "Surquillo, Lima"
    assert d["icono"] == "store"
    assert d["archivo_url"] == "/api/lecciones/datasets/bodega/archivo"
    assert [t["nombre"] for t in d["tablas"]] == ["productos", "clientes", "ventas"]
    productos = d["tablas"][0]
    assert productos["filas_total"] == 12
    assert productos["columnas"][3] == {"nombre": "precio", "tipo": "DECIMAL"}
    assert productos["muestra"]["columnas"] == ["id", "nombre", "categoria", "precio", "stock"]
    assert len(productos["muestra"]["filas"]) == 5
    assert productos["muestra"]["filas"][0] == [1, "Inca Kola 500 ml", "Bebidas", 3.5, 48]
    assert "archivo" not in d  # los bytes solo salen por /archivo


def test_iconos_de_los_datasets(client: TestClient, sembrado: ContenidoConstruido) -> None:
    iconos = {
        s: client.get(f"{P}/datasets/{s}").json()["icono"]
        for s in ("bodega", "delivery", "campanas")
    }
    assert iconos == {"bodega": "store", "delivery": "bike", "campanas": "megaphone"}


def test_dataset_no_existe(client: TestClient, sembrado: ContenidoConstruido) -> None:
    for ruta in (f"{P}/datasets/nada", f"{P}/datasets/nada/archivo"):
        r = client.get(ruta)
        assert r.status_code == 404
        assert r.json()["error"]["codigo"] == "DATASET_NO_EXISTE"


def test_archivo_headers_y_sqlite_valido(client: TestClient, sembrado: ContenidoConstruido) -> None:
    sha = client.get(f"{P}/datasets/bodega").json()["archivo_sha256"]
    r = client.get(f"{P}/datasets/bodega/archivo")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/vnd.sqlite3"
    assert r.headers["cache-control"] == "public, max-age=3600"
    assert r.headers["etag"] == f'"{sha}"'
    assert hashlib.sha256(r.content).hexdigest() == sha
    assert r.content[:15] == b"SQLite format 3"

    conn = sqlite3.connect(":memory:")
    conn.deserialize(r.content)
    assert conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0] == 12
    assert conn.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] == 15
    assert conn.execute("SELECT nombre FROM clientes WHERE id = 1").fetchone()[0] == "Lucía Quispe"
    conn.close()


@pytest.mark.parametrize("slug", ["bodega", "delivery", "campanas"])
def test_archivo_de_cada_dataset_abre(
    client: TestClient, sembrado: ContenidoConstruido, slug: str
) -> None:
    conn = sqlite3.connect(":memory:")
    conn.deserialize(client.get(f"{P}/datasets/{slug}/archivo").content)
    tablas = {n for (n,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    esperadas = {t["nombre"] for t in client.get(f"{P}/datasets/{slug}").json()["tablas"]}
    assert tablas == esperadas
    conn.close()


@pytest.mark.parametrize(
    "cabecera",
    ["{etag}", "W/{etag}", '"otro", {etag}', "*"],
)
def test_archivo_304_si_coincide_if_none_match(
    client: TestClient, sembrado: ContenidoConstruido, cabecera: str
) -> None:
    etag = client.get(f"{P}/datasets/delivery/archivo").headers["etag"]
    r = client.get(
        f"{P}/datasets/delivery/archivo", headers={"If-None-Match": cabecera.format(etag=etag)}
    )
    assert r.status_code == 304
    assert r.content == b""
    assert r.headers["etag"] == etag
    assert r.headers["cache-control"] == "public, max-age=3600"


def test_archivo_200_si_el_etag_no_coincide(
    client: TestClient, sembrado: ContenidoConstruido
) -> None:
    r = client.get(f"{P}/datasets/delivery/archivo", headers={"If-None-Match": '"viejo"'})
    assert r.status_code == 200 and len(r.content) > 0


# --- Público: el JWT se ignora ---------------------------------------------------------------


def test_endpoints_publicos_sin_token(client: TestClient, sembrado: ContenidoConstruido) -> None:
    for ruta in (
        f"{P}/modulos",
        f"{P}/lecciones/where",
        f"{P}/ejercicios/where-1",
        f"{P}/datasets/bodega",
    ):
        assert client.get(ruta).status_code == 200


@pytest.mark.parametrize("modo", ["basura", "expirado", "otro_secreto"])
def test_jwt_invalido_se_ignora(
    client: TestClient, sembrado: ContenidoConstruido, modo: str
) -> None:
    if modo == "basura":
        token = "esto.no.es.un.jwt"
    elif modo == "expirado":
        token = emitir_token("11111111-1111-4111-8111-111111111111", "a@b.pe", "Ana", exp_horas=-1)
    else:
        token = emitir_token(
            "11111111-1111-4111-8111-111111111111", "a@b.pe", "Ana", secret="otro" * 10
        )
    for ruta in (
        f"{P}/modulos",
        f"{P}/lecciones/where",
        f"{P}/ejercicios/where-1",
        f"{P}/datasets/bodega",
    ):
        r = client.get(ruta, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, (ruta, modo)


def test_jwt_valido_tambien_funciona(client: TestClient, sembrado: ContenidoConstruido) -> None:
    token = emitir_token("11111111-1111-4111-8111-111111111111", "a@b.pe", "Ana")
    r = client.get(f"{P}/modulos", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


# --- /interno/estructura ---------------------------------------------------------------------


def _estructura(client: TestClient) -> dict[str, Any]:
    r = client.get("/interno/estructura")
    assert r.status_code == 200
    return r.json()


def test_estructura_forma(client: TestClient, sembrado: ContenidoConstruido) -> None:
    d = _estructura(client)
    assert set(d) == {"version", "modulos"}
    assert len(d["version"]) == 64 and int(d["version"], 16) >= 0
    assert [m["slug"] for m in d["modulos"]] == ["basico", "intermedio", "avanzado"]
    basico = d["modulos"][0]
    assert set(basico) == {"slug", "nombre", "orden", "lecciones"}
    assert basico["nombre"] == "Básico" and basico["orden"] == 1
    assert basico["lecciones"][0] == {
        "slug": "select-from",
        "orden": 1,
        "ejercicios": ["select-from-1", "select-from-2"],
    }
    assert sum(len(x["ejercicios"]) for m in d["modulos"] for x in m["lecciones"]) == 16


def test_estructura_version_es_el_sha256_de_la_estructura(
    client: TestClient, sembrado: ContenidoConstruido
) -> None:
    d = _estructura(client)
    canonico = json.dumps(d["modulos"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert d["version"] == hashlib.sha256(canonico.encode()).hexdigest()


def test_estructura_version_estable_y_cambia_con_la_estructura(
    client: TestClient, sembrado: ContenidoConstruido, motor: Engine
) -> None:
    antes = _estructura(client)
    assert _estructura(client)["version"] == antes["version"]
    with Session(motor) as db, db.begin():
        db.execute(delete(Ejercicio).where(Ejercicio.id == "metricas-2"))
    despues = _estructura(client)
    assert despues["version"] != antes["version"]
    assert despues["modulos"][2]["lecciones"][1]["ejercicios"] == ["metricas-1"]


def test_estructura_no_se_expone_bajo_el_prefijo_publico(
    client: TestClient, sembrado: ContenidoConstruido
) -> None:
    assert client.get(f"{P}/interno/estructura").status_code == 404
    assert client.get(f"{P}/estructura").status_code == 404


def test_estructura_no_filtra_solucion(client: TestClient, sembrado: ContenidoConstruido) -> None:
    assert "solucion" not in client.get("/interno/estructura").text.lower()
