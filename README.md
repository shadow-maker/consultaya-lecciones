# consultaya-lecciones

Microservicio de lecciones: módulos, lecciones, ejercicios, datasets y el contenido del curso (con su seed).

Parte de **ConsultaYa**, una plataforma web para aprender SQL practicando, en español, con datos de negocios latinoamericanos. La especificación completa está en `../docs/` del workspace (contrato de API en `../docs/02-contratos-api.md`).

Stack: Python 3.12, FastAPI, SQLAlchemy 2 (síncrono), Alembic, psycopg 3, PyJWT, uv.

> Estado: esqueleto de microservicio (health, errores estándar, validación de JWT, Alembic y tests). La lógica de lecciones (contenido, seed y endpoints) llega en la Ola 2.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (descarga Python 3.12 solo, según `.python-version`).
- PostgreSQL local en `localhost:5432` (usuario `ca`, sin contraseña) con las bases `consultaya_lecciones` y `consultaya_lecciones_test` (las crea `consultaya-deploy/scripts/db-local-init.sh`).

## Cómo correr (modo nativo, puerto 8002)

```bash
cp .env.example .env          # los valores locales ya vienen listos
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --port 8002 --reload
```

- Health: <http://localhost:8002/health> y <http://localhost:8002/api/lecciones/health>
- Documentación OpenAPI: <http://localhost:8002/api/lecciones/docs>

## Tests y calidad

```bash
uv run pytest                  # Postgres real, base consultaya_lecciones_test
uv run ruff check .
uv run ruff format --check .
```

Los tests recrean el esquema de la base `_test` con Alembic (`DROP SCHEMA public CASCADE`, protegido para que solo funcione sobre bases `consultaya_*_test`) y hacen `TRUNCATE` entre tests. Si no hay `.env`, usan los valores locales por defecto.

## Migraciones

```bash
uv run alembic revision --autogenerate -m "descripción"   # formatea la revisión con ruff
uv run alembic upgrade head
```

## Docker

```bash
docker build -t consultaya-lecciones .
```

El contenedor escucha en el puerto **8000** y ejecuta `alembic upgrade head` antes de arrancar `uvicorn`. Las variables se pasan con `--env-file` (en el despliegue las gestiona `consultaya-deploy`).

## Variables de entorno

| Variable | Ejemplo local | Notas |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://ca@localhost:5432/consultaya_lecciones` | En Docker local: host `host.docker.internal`. |
| `TEST_DATABASE_URL` | `postgresql+psycopg://ca@localhost:5432/consultaya_lecciones_test` | Solo tests. Debe terminar en `_test`. |
| `JWT_SECRET` | `dev-secret-cambiar` | Mismo valor en los 3 servicios. En AWS, aleatorio de 64+ caracteres. |
| `LOG_LEVEL` | `INFO` | |

## Estructura

```
app/
  config.py    SERVICIO, prefijo /api/<servicio>, settings (pydantic-settings)
  main.py      create_app(): docs/openapi bajo el prefijo, routers, manejadores de error
  db.py        engine, SessionLocal, Base, get_db
  errors.py    ApiError + formato de error estándar (401/404/422/500)
  auth.py      emitir_token, validar_token, dependencia usuario_actual
  models.py    modelos ORM (importarlos aquí para Alembic)
  schemas.py   schemas Pydantic
  routers/     un módulo por recurso (health incluido)
alembic/       migraciones
scripts/       seeds y utilidades
tests/         pytest
```

## Convenciones de errores

Todas las respuestas de error usan `{"error": {"codigo", "mensaje", "campos"}}`:

- En endpoints: `raise ApiError(409, "CORREO_EN_USO", "Este correo ya está en uso.")`.
- En validadores Pydantic: `raise ValueError("Ingresa tus nombres.")` se convierte en el mensaje del campo dentro de `campos` (422 `VALIDACION`).
