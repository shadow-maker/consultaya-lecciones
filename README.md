# consultaya-lecciones

Microservicio de lecciones: módulos, lecciones, ejercicios, datasets y el contenido del curso (con su seed).

Parte de **ConsultaYa**, una plataforma web para aprender SQL practicando, en español, con datos de negocios latinoamericanos. La especificación completa está en `../docs/` del workspace (contrato de API en `../docs/02-contratos-api.md`).

Stack: Python 3.12, FastAPI, SQLAlchemy 2 (síncrono), Alembic, psycopg 3, PyJWT, uv.

Contenido: 3 módulos, 3 datasets (con su archivo `.sqlite`), 8 lecciones y 16 ejercicios, que viven como código en `contenido/` y se cargan a Postgres con `scripts/seed.py`.

## Endpoints

Contrato completo: `../docs/02-contratos-api.md` (sección "Servicio lecciones"). Los `GET /api/lecciones/*` son públicos (un JWT inválido se ignora).

| Método y ruta | Descripción |
|---|---|
| `GET /api/lecciones/modulos` | Módulos con sus lecciones y los ids de ejercicios |
| `GET /api/lecciones/lecciones/{slug}` | Lección con secciones (ejemplos ya ejecutados), `anterior` y `siguiente` |
| `GET /api/lecciones/ejercicios/{id}` | Enunciado y resultado esperado (**nunca** la solución) |
| `GET /api/lecciones/datasets/{slug}` | Metadatos y tablas (con muestra de 5 filas) |
| `GET /api/lecciones/datasets/{slug}/archivo` | Bytes del `.sqlite`, con `ETag` y `304` |
| `GET /interno/estructura` | Solo red interna (la consume `progreso`); no se publica por nginx |

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

## Contenido y seed

```bash
uv run alembic upgrade head
uv run python scripts/seed.py      # imprime: 3 módulos · 3 datasets · 8 lecciones · 16 ejercicios
```

El seed valida `contenido/` (slugs y `orden` únicos, referencias a módulo y dataset, al menos un ejemplo y un ejercicio por lección), construye cada dataset con `sqlite3` en memoria (`contenido/datasets/<slug>.sql`), ejecuta cada ejemplo y cada solución para guardar los resultados, y escribe todo en **una sola transacción**: es idempotente (upsert por slug/id y borra lo que ya no existe) y, si algo falla, no escribe nada. Formato de `contenido/`: `../docs/04-contenido.md`. En Docker corre con `python scripts/seed.py` dentro del contenedor.

Para añadir una lección: crea `contenido/lecciones/NN-<slug>.yaml`, ejecuta el seed y listo (los ejemplos y soluciones se ejecutan contra SQLite, igual que en el navegador con sql.js).

## Tests y calidad

```bash
uv run pytest                  # Postgres real, base consultaya_lecciones_test
uv run ruff check .
uv run ruff format --check .
```

Los tests siembran el contenido real en la base `_test` (nunca dependen del seed de desarrollo). Recrean el esquema de la base `_test` con Alembic (`DROP SCHEMA public CASCADE`, protegido para que solo funcione sobre bases `consultaya_*_test`) y hacen `TRUNCATE` entre tests. Si no hay `.env`, usan los valores locales por defecto.

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
  routers/     health y `lecciones` (endpoints públicos e interno)
  contenido.py carga, validación y ejecución con SQLite del contenido (sin tocar Postgres)
  sembrar.py   upsert transaccional del contenido en Postgres
alembic/       migraciones
contenido/     módulos, datasets (.yaml + .sql) y lecciones (.yaml)
scripts/       seed.py (siembra el contenido)
tests/         pytest
```

## Convenciones de errores

Todas las respuestas de error usan `{"error": {"codigo", "mensaje", "campos"}}`:

- En endpoints: `raise ApiError(409, "CORREO_EN_USO", "Este correo ya está en uso.")`.
- En validadores Pydantic: `raise ValueError("Ingresa tus nombres.")` se convierte en el mensaje del campo dentro de `campos` (422 `VALIDACION`).
