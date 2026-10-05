# consultaya-lecciones

Microservicio de **lecciones** de ConsultaYa: módulos, lecciones, ejercicios y datasets (con su archivo `.sqlite`). El contenido del curso vive como código en `contenido/` y se carga a Postgres con `scripts/seed.py`.

**ConsultaYa** es una plataforma web para aprender SQL practicando, en español, con datos de negocios latinoamericanos. Este repo es una pieza del sistema:

| Repo | Rol |
|---|---|
| [`consultaya-usuarios`](https://github.com/shadow-maker/consultaya-usuarios) | Registro, login, JWT y perfil (puerto local 8001) |
| **`consultaya-lecciones`** (este) | Contenido: módulos, lecciones, ejercicios y datasets (puerto local 8002) |
| [`consultaya-progreso`](https://github.com/shadow-maker/consultaya-progreso) | Ejercicios completados, estados de la ruta y resumen (puerto local 8003). Consume `GET /interno/estructura` de este servicio |
| [`consultaya-frontend`](https://github.com/shadow-maker/consultaya-frontend) | App web (React + Vite); consume los endpoints públicos de este servicio (puerto local 5173) |
| [`consultaya-deploy`](https://github.com/shadow-maker/consultaya-deploy) | Docker Compose, nginx, scripts de desarrollo local y de despliegue, pruebas e2e |

Stack: Python 3.12, FastAPI, SQLAlchemy 2 (síncrono), Alembic, psycopg 3, PyJWT, PyYAML, uv.

Documentación de este repo:

- [`docs/api.md`](docs/api.md): endpoints, objetos, errores, ETag/304.
- [`docs/contenido.md`](docs/contenido.md): formato de `contenido/`, cómo agregar lecciones y qué hace el seed.

## Requisitos

- [uv](https://docs.astral.sh/uv/getting-started/installation/): descarga Python 3.12 solo (según `.python-version`).
- PostgreSQL local en `localhost:5432` (con permisos para crear bases).
- git. Funciona igual en macOS, Linux y Windows.

## Puesta en marcha (puerto 8002)

### 1. Bases de datos

Crea dos bases vacías (desarrollo y tests). Con `psql` (macOS, Linux y Windows; ajusta usuario y host):

```bash
psql -h localhost -U TU_USUARIO -d postgres -c "CREATE DATABASE consultaya_lecciones;"
psql -h localhost -U TU_USUARIO -d postgres -c "CREATE DATABASE consultaya_lecciones_test;"
```

Si usas el repo `consultaya-deploy`, su script de inicialización de bases (`scripts/db-local-init.sh`) las crea por ti.

### 2. Archivo `.env`

Cópialo desde el ejemplo y reemplaza `USUARIO` y `PASSWORD` (o quita `:PASSWORD` si tu usuario no tiene contraseña):

```bash
# macOS / Linux
cp .env.example .env
```

```powershell
# Windows (PowerShell)
Copy-Item .env.example .env
```

El `.env` no se sube a git. También puede generarlo `consultaya-deploy` (`scripts/dev-up`) a partir de `.env.example`.

### 3. Instalar, migrar, sembrar y arrancar

Los comandos son los mismos en macOS, Linux y Windows (PowerShell):

```bash
uv sync
uv run alembic upgrade head
uv run python scripts/seed.py     # imprime: 3 módulos · 3 datasets · 8 lecciones · 16 ejercicios
uv run uvicorn app.main:app --port 8002 --reload
```

- Health: <http://localhost:8002/health> y <http://localhost:8002/api/lecciones/health>
- OpenAPI interactivo: <http://localhost:8002/api/lecciones/docs>

## Tests y calidad

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

- Los tests usan Postgres real, en la base de `TEST_DATABASE_URL` (del entorno o del `.env`). Si falta, `pytest` termina enseguida con un mensaje que lo explica.
- **Atención:** los tests ejecutan `DROP SCHEMA public CASCADE` sobre esa base. Por seguridad solo la aceptan si se llama `consultaya_*_test`.
- Los tests siembran el contenido real en la base `_test`; no dependen del seed de desarrollo.

## Contenido y seed

```bash
uv run python scripts/seed.py
```

El seed valida `contenido/`, construye cada dataset con `sqlite3` en memoria, ejecuta cada ejemplo y cada solución para guardar los resultados, y escribe todo en **una sola transacción**. Es idempotente (se puede correr las veces que quieras) y, si algo falla, no escribe nada. Detalles y formato: [`docs/contenido.md`](docs/contenido.md).

## Endpoints

Detalle completo en [`docs/api.md`](docs/api.md). Los `GET /api/lecciones/*` son públicos (un JWT inválido se ignora).

| Método y ruta | Descripción |
|---|---|
| `GET /api/lecciones/modulos` | Módulos con sus lecciones y los ids de ejercicios |
| `GET /api/lecciones/lecciones/{slug}` | Lección con secciones (ejemplos ya ejecutados), `anterior` y `siguiente` |
| `GET /api/lecciones/ejercicios/{id}` | Enunciado y resultado esperado (**nunca** la solución) |
| `GET /api/lecciones/datasets/{slug}` | Metadatos y tablas (con muestra de 5 filas) |
| `GET /api/lecciones/datasets/{slug}/archivo` | Bytes del `.sqlite`, con `ETag` y `304` |
| `GET /interno/estructura` | Solo red interna (la consume `progreso`); nginx no la publica |

## Modelo de datos

### Base `consultaya_lecciones` (Postgres)

Cuatro tablas, creadas por la migración de Alembic. Una lección pertenece a un módulo y usa un dataset; cada lección tiene varios ejercicios. Todo lo llena `scripts/seed.py` desde `contenido/`.

```mermaid
erDiagram
    modulos ||--o{ lecciones : "tiene"
    datasets ||--o{ lecciones : "usan"
    lecciones ||--o{ ejercicios : "tiene"

    modulos {
        varchar slug PK "basico, intermedio, avanzado"
        varchar nombre
        text descripcion
        int orden UK
    }
    datasets {
        varchar slug PK "bodega, delivery, campanas"
        varchar nombre
        varchar lugar
        text descripcion
        varchar icono
        jsonb tablas "lista de DatasetTabla"
        bytea archivo "archivo .sqlite generado por el seed"
        varchar archivo_sha256
    }
    lecciones {
        varchar slug PK
        varchar modulo_slug FK
        int orden UK "orden global en la ruta"
        varchar titulo
        text resumen
        int duracion_min
        varchar dataset_slug FK
        text_array tags
        text_array aprenderas
        jsonb secciones "lista de Seccion con resultados de ejemplo"
    }
    ejercicios {
        varchar id PK "leccion_slug-n, por ejemplo where-2"
        varchar leccion_slug FK "UK junto con orden"
        int orden "UK junto con leccion_slug"
        text enunciado_md
        text solucion_sql "nunca se expone por la API"
        boolean ordenado
        jsonb resultado_esperado "ResultadoSQL calculado por el seed"
    }
```

- `ejercicios.solucion_sql` se guarda para que el seed calcule `resultado_esperado`, pero **nunca** sale por la API.
- `datasets.archivo` guarda el archivo `.sqlite` que genera el seed (se sirve con ETag desde `/api/lecciones/datasets/{slug}/archivo`); `archivo_sha256` es su huella y su ETag.
- [`consultaya-progreso`](https://github.com/shadow-maker/consultaya-progreso) no accede a esta base: consume `GET /interno/estructura` y guarda sus propios datos (ejercicios completados) referenciando los ids de ejercicios y lecciones de aquí.

### Tablas de los datasets (SQLite, las que consulta el estudiante)

Estas tablas **no están en Postgres**: viven dentro del archivo `.sqlite` de cada dataset (`contenido/datasets/<slug>.sql`). El navegador descarga el archivo y ejecuta las consultas con sql.js. Los tipos de abajo son los del `.sql` (`REAL` y `TEXT`); a la persona que estudia se le muestran como `DECIMAL` y `DATE`. El `.sql` no declara claves foráneas, pero las relaciones son las que se ven en los diagramas y es lo que se usa en los `JOIN`.

**Dataset `bodega`** (Bodega Doña Rosa)

```mermaid
erDiagram
    productos ||--o{ ventas : "producto_id"
    clientes ||--o{ ventas : "cliente_id"

    productos {
        INTEGER id PK
        TEXT nombre
        TEXT categoria
        REAL precio
        INTEGER stock
    }
    clientes {
        INTEGER id PK
        TEXT nombre
        TEXT distrito
    }
    ventas {
        INTEGER id PK
        INTEGER producto_id FK
        INTEGER cliente_id FK
        INTEGER cantidad
        TEXT fecha
    }
```

**Dataset `delivery`** (RapiMenú)

```mermaid
erDiagram
    restaurantes ||--o{ pedidos : "restaurante_id"

    restaurantes {
        INTEGER id PK
        TEXT nombre
        TEXT tipo_cocina
        TEXT distrito
    }
    pedidos {
        INTEGER id PK
        INTEGER restaurante_id FK
        TEXT distrito
        REAL monto
        TEXT estado
        TEXT fecha
    }
```

**Dataset `campanas`** (Campañas de TiendaNova): una sola tabla.

```mermaid
erDiagram
    campanas {
        INTEGER id PK
        TEXT nombre
        TEXT canal
        REAL presupuesto
        INTEGER clics
        INTEGER conversiones
        TEXT mes
    }
```

## Variables de entorno

| Variable | Ejemplo | Notas |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://USUARIO:PASSWORD@localhost:5432/consultaya_lecciones` | Base del servicio. En Docker con Postgres en el host: host `host.docker.internal`. |
| `TEST_DATABASE_URL` | `postgresql+psycopg://USUARIO:PASSWORD@localhost:5432/consultaya_lecciones_test` | Solo tests. Debe llamarse `consultaya_*_test`. |
| `JWT_SECRET` | `dev-secret-cambiar` | El mismo valor en los 3 servicios. En AWS, aleatorio de 64+ caracteres. |
| `LOG_LEVEL` | `INFO` | Nivel de `logging`. |

## Docker

```bash
docker build -t consultaya-lecciones .
docker run --rm -p 8002:8000 --env-file .env consultaya-lecciones
```

- La imagen (`python:3.12-slim`, usuario no root) copia `app/`, `alembic/`, `scripts/` y `contenido/`, escucha en el puerto **8000** y ejecuta `alembic upgrade head` antes de arrancar `uvicorn`.
- Las variables se pasan con `--env-file`; dentro del contenedor `DATABASE_URL` debe apuntar a un Postgres alcanzable desde él (por ejemplo `host.docker.internal`).
- El seed no corre solo al arrancar: ejecútalo dentro del contenedor, con `docker exec <contenedor> python scripts/seed.py`. En el despliegue lo orquesta `consultaya-deploy`.
- Healthcheck: `GET /health`.

## Migraciones

```bash
uv run alembic revision --autogenerate -m "descripción"   # formatea la revisión con ruff
uv run alembic upgrade head
```

## Estructura

```
app/
  config.py      SERVICIO, prefijo /api/lecciones, settings (pydantic-settings)
  main.py        create_app(): docs/openapi bajo el prefijo, routers, manejadores de error
  db.py          engine, SessionLocal, Base, get_db
  errors.py      ApiError + formato de error estándar
  auth.py        validación de JWT (emitir_token se usa solo en tests)
  models.py      modelos ORM: Modulo, Dataset, Leccion, Ejercicio
  schemas.py     schemas Pydantic de respuesta
  contenido.py   carga, validación y ejecución con SQLite del contenido (sin tocar Postgres)
  sembrar.py     upsert transaccional del contenido en Postgres
  routers/       health y lecciones (endpoints públicos e interno)
alembic/         migraciones
contenido/       módulos, datasets (.yaml + .sql) y lecciones (.yaml)
scripts/         seed.py
docs/            api.md y contenido.md
tests/           pytest
```

## Errores

Todas las respuestas de error usan `{"error": {"codigo", "mensaje", "campos"}}` (ver [`docs/api.md`](docs/api.md)). En endpoints: `raise ApiError(404, "LECCION_NO_EXISTE", "La lección que buscas no existe.")`.
