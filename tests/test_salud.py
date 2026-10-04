from fastapi.testclient import TestClient

from app.config import PREFIJO, SERVICIO


def test_health_raiz(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "servicio": SERVICIO}


def test_health_con_prefijo(client: TestClient) -> None:
    r = client.get(f"{PREFIJO}/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "servicio": SERVICIO}


def test_docs_y_openapi_bajo_el_prefijo(client: TestClient) -> None:
    assert client.get(f"{PREFIJO}/docs").status_code == 200
    r = client.get(f"{PREFIJO}/openapi.json")
    assert r.status_code == 200
    assert f"{PREFIJO}/health" in r.json()["paths"]
    # Las rutas por defecto de FastAPI no deben quedar expuestas.
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_base_de_datos_de_pruebas_responde(db) -> None:  # type: ignore[no-untyped-def]
    from sqlalchemy import text

    assert db.execute(text("SELECT 1")).scalar() == 1
