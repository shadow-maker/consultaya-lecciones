from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, field_validator

from app.config import PREFIJO
from app.errors import ApiError


class _Entrada(BaseModel):
    nombres: str
    edad: int

    @field_validator("nombres")
    @classmethod
    def _nombres(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Ingresa tus nombres.")
        return v


def _con_rutas_de_prueba(app: FastAPI) -> TestClient:
    @app.post(f"{PREFIJO}/_prueba/validar")
    def validar(datos: _Entrada) -> dict[str, str]:
        return {"nombres": datos.nombres}

    @app.get(f"{PREFIJO}/_prueba/conflicto")
    def conflicto() -> None:
        raise ApiError(409, "CORREO_EN_USO", "Este correo ya está en uso.")

    @app.get(f"{PREFIJO}/_prueba/explota")
    def explota() -> None:
        raise RuntimeError("secreto interno: postgresql://ca@localhost/x")

    return TestClient(app, raise_server_exceptions=False)


def test_404_formato_estandar(client: TestClient) -> None:
    r = client.get(f"{PREFIJO}/no-existe")
    assert r.status_code == 404
    error = r.json()["error"]
    assert error["codigo"] == "NO_ENCONTRADO"
    assert error["mensaje"]
    assert error["campos"] is None


def test_405_formato_estandar(client: TestClient) -> None:
    r = client.post(f"{PREFIJO}/health")
    assert r.status_code == 405
    assert r.json()["error"]["codigo"] == "METODO_NO_PERMITIDO"


def test_422_con_campos_en_espanol(app: FastAPI) -> None:
    c = _con_rutas_de_prueba(app)
    r = c.post(f"{PREFIJO}/_prueba/validar", json={"nombres": "   ", "edad": "x"})
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["codigo"] == "VALIDACION"
    assert error["mensaje"]
    assert error["campos"]["nombres"] == "Ingresa tus nombres."
    assert error["campos"]["edad"] == "Debe ser un número entero."


def test_422_campo_faltante(app: FastAPI) -> None:
    c = _con_rutas_de_prueba(app)
    r = c.post(f"{PREFIJO}/_prueba/validar", json={})
    assert r.status_code == 422
    assert r.json()["error"]["campos"] == {
        "nombres": "Este campo es obligatorio.",
        "edad": "Este campo es obligatorio.",
    }


def test_422_sin_cuerpo_y_json_roto(app: FastAPI) -> None:
    c = _con_rutas_de_prueba(app)
    r = c.post(f"{PREFIJO}/_prueba/validar")
    assert r.status_code == 422
    assert r.json()["error"]["codigo"] == "VALIDACION"
    assert "cuerpo" in r.json()["error"]["campos"]
    r = c.post(
        f"{PREFIJO}/_prueba/validar", content="{roto", headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 422
    assert "cuerpo" in r.json()["error"]["campos"]


def test_422_no_filtra_el_valor_enviado(app: FastAPI) -> None:
    c = _con_rutas_de_prueba(app)
    r = c.post(f"{PREFIJO}/_prueba/validar", json={"nombres": "Ana", "edad": "clave-secreta-123"})
    assert "clave-secreta-123" not in r.text


def test_api_error_de_negocio(app: FastAPI) -> None:
    c = _con_rutas_de_prueba(app)
    r = c.get(f"{PREFIJO}/_prueba/conflicto")
    assert r.status_code == 409
    assert r.json() == {
        "error": {
            "codigo": "CORREO_EN_USO",
            "mensaje": "Este correo ya está en uso.",
            "campos": None,
        }
    }


def test_500_sin_stack_trace(app: FastAPI) -> None:
    c = _con_rutas_de_prueba(app)
    r = c.get(f"{PREFIJO}/_prueba/explota")
    assert r.status_code == 500
    assert r.json()["error"]["codigo"] == "ERROR_INTERNO"
    assert r.json()["error"]["campos"] is None
    assert "secreto" not in r.text
    assert "Traceback" not in r.text
