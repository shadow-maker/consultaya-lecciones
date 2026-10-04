from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import UsuarioToken, emitir_token, usuario_actual, validar_token
from app.config import JWT_ISSUER, PREFIJO, get_settings
from app.errors import ApiError

RUTA = f"{PREFIJO}/_prueba/protegida"


@pytest.fixture
def cliente_auth(app: FastAPI) -> TestClient:
    @app.get(RUTA)
    def protegida(usuario: UsuarioToken = Depends(usuario_actual)) -> dict[str, str]:
        return {"id": str(usuario.id), "email": usuario.email, "nombres": usuario.nombres}

    return TestClient(app, raise_server_exceptions=False)


def _assert_no_autenticado(r) -> None:  # type: ignore[no-untyped-def]
    assert r.status_code == 401
    error = r.json()["error"]
    assert error["codigo"] == "NO_AUTENTICADO"
    assert error["mensaje"]
    assert error["campos"] is None


def test_token_valido(cliente_auth: TestClient) -> None:
    uid = uuid4()
    token = emitir_token(uid, "demo@consultaya.pe", "Ana Torres")
    r = cliente_auth.get(RUTA, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"id": str(uid), "email": "demo@consultaya.pe", "nombres": "Ana Torres"}


def test_sin_token(cliente_auth: TestClient) -> None:
    _assert_no_autenticado(cliente_auth.get(RUTA))


def test_esquema_distinto_de_bearer(cliente_auth: TestClient) -> None:
    _assert_no_autenticado(cliente_auth.get(RUTA, headers={"Authorization": "Basic abc"}))


def test_token_basura(cliente_auth: TestClient) -> None:
    _assert_no_autenticado(cliente_auth.get(RUTA, headers={"Authorization": "Bearer basura"}))


def test_token_expirado(cliente_auth: TestClient) -> None:
    token = emitir_token(uuid4(), "a@b.pe", "Ana", exp_horas=-1)
    _assert_no_autenticado(cliente_auth.get(RUTA, headers={"Authorization": f"Bearer {token}"}))


def test_firma_con_otro_secreto(cliente_auth: TestClient) -> None:
    token = emitir_token(uuid4(), "a@b.pe", "Ana", secret="otro-secreto-distinto-de-32-bytes!!")
    _assert_no_autenticado(cliente_auth.get(RUTA, headers={"Authorization": f"Bearer {token}"}))


def _token_manual(**cambios: object) -> str:
    ahora = datetime.now(UTC)
    claims: dict[str, object] = {
        "sub": str(uuid4()),
        "email": "a@b.pe",
        "nombres": "Ana",
        "iat": ahora,
        "exp": ahora + timedelta(hours=1),
        "iss": JWT_ISSUER,
    }
    claims.update(cambios)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, get_settings().jwt_secret, algorithm="HS256")


def test_issuer_incorrecto(cliente_auth: TestClient) -> None:
    token = _token_manual(iss="otro-servicio")
    _assert_no_autenticado(cliente_auth.get(RUTA, headers={"Authorization": f"Bearer {token}"}))


def test_sin_issuer_ni_exp(cliente_auth: TestClient) -> None:
    for faltante in ("iss", "exp", "sub"):
        token = _token_manual(**{faltante: None})
        _assert_no_autenticado(cliente_auth.get(RUTA, headers={"Authorization": f"Bearer {token}"}))


def test_sub_no_es_uuid(cliente_auth: TestClient) -> None:
    token = _token_manual(sub="no-es-uuid")
    _assert_no_autenticado(cliente_auth.get(RUTA, headers={"Authorization": f"Bearer {token}"}))


def test_algoritmo_none_rechazado(cliente_auth: TestClient) -> None:
    ahora = datetime.now(UTC)
    token = jwt.encode(
        {"sub": str(uuid4()), "exp": ahora + timedelta(hours=1), "iss": JWT_ISSUER},
        key=None,
        algorithm="none",
    )
    _assert_no_autenticado(cliente_auth.get(RUTA, headers={"Authorization": f"Bearer {token}"}))


def test_emitir_token_incluye_los_claims_del_contrato() -> None:
    uid = uuid4()
    ahora = datetime(2026, 9, 18, 19, 12, tzinfo=UTC)
    token = emitir_token(uid, "demo@consultaya.pe", "Ana Torres", ahora=ahora)
    claims = jwt.decode(
        token, get_settings().jwt_secret, algorithms=["HS256"], options={"verify_exp": False}
    )
    assert set(claims) == {"sub", "email", "nombres", "iat", "exp", "iss"}
    assert claims["sub"] == str(uid)
    assert claims["iss"] == "consultaya-usuarios"
    assert claims["exp"] - claims["iat"] == get_settings().jwt_exp_horas * 3600


def test_validar_token_devuelve_usuario_y_falla_con_api_error() -> None:
    uid = uuid4()
    usuario = validar_token(emitir_token(uid, "a@b.pe", "Ana"))
    assert usuario == UsuarioToken(id=UUID(str(uid)), email="a@b.pe", nombres="Ana")
    with pytest.raises(ApiError) as exc:
        validar_token("x.y.z")
    assert exc.value.status_code == 401
    assert exc.value.codigo == "NO_AUTENTICADO"
