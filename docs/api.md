# API del servicio de lecciones

Servicio `lecciones` de ConsultaYa. Puerto local 8002 (8000 dentro de Docker). Este documento describe lo que implementa este repo (parte de lecciones del contrato de ConsultaYa, v1.2); los demás servicios y el frontend se integran solo a través de estos formatos.

## Convenciones

- JSON en `snake_case`, UTF-8.
- Rutas públicas bajo el prefijo `/api/lecciones/...` (así nginx hace `proxy_pass` sin reescribir). Rutas internas bajo `/interno/...`, sin `/api`.
- Health: `GET /health` y `GET /api/lecciones/health` → `200 {"status":"ok","servicio":"lecciones"}`.
- OpenAPI automático: `/api/lecciones/docs` (JSON en `/api/lecciones/openapi.json`).
- **Lectura pública:** todos los `GET /api/lecciones/*` funcionan sin autenticación. Si se envía un header `Authorization: Bearer <JWT>`, se ignora (válido o no). El contenido no es sensible; el frontend exige sesión para navegar.
- **`solucion_sql` nunca sale por la API.** Ninguna respuesta (públicas ni interna) la incluye, y los schemas de respuesta no tienen ese campo. Un test lo verifica sobre todos los endpoints.

## Formato de error estándar

```json
{ "error": { "codigo": "LECCION_NO_EXISTE", "mensaje": "La lección que buscas no existe.", "campos": null } }
```

- `codigo`: constante en MAYÚSCULAS (quien consume decide por `codigo`, nunca por el texto).
- `mensaje`: texto en español listo para mostrar.
- `campos`: solo en `422` (ningún endpoint de este servicio recibe cuerpo, así que en la práctica es `null`).

| HTTP | `codigo` | Cuándo |
|---|---|---|
| 404 | `LECCION_NO_EXISTE` | `GET /lecciones/{slug}` con un slug inexistente |
| 404 | `EJERCICIO_NO_EXISTE` | `GET /ejercicios/{id}` con un id inexistente |
| 404 | `DATASET_NO_EXISTE` | `GET /datasets/{slug}` y `/datasets/{slug}/archivo` con un slug inexistente |
| 404 | `NO_ENCONTRADO` | Ruta inexistente |
| 405 | `METODO_NO_PERMITIDO` | Método no permitido |
| 500 | `ERROR_INTERNO` | Inesperado (sin stack trace en la respuesta) |

También existen los genéricos `400 SOLICITUD_INVALIDA`, `403 PROHIBIDO` y `ERROR_HTTP` (cualquier otro estado), que emite el manejador común.

## Objetos

```jsonc
// ResultadoSQL: valores tal como los devuelve sqlite3 (int, float, str o null)
{ "columnas": ["nombre", "precio"], "filas": [["Inca Kola 500 ml", 3.5], ["Coca-Cola 1.5 L", 7.0]] }

// Seccion
{ "orden": 1, "titulo": "La cláusula WHERE", "cuerpo_md": "Muchas veces...",
  "ejemplo": { "sql": "SELECT ...", "nota": "texto o null", "resultado": ResultadoSQL },  // o "ejemplo": null
  "tip": "texto o null" }

// DatasetTabla
{ "nombre": "productos", "descripcion": "Catálogo de productos...", "filas_total": 12,
  "columnas": [ { "nombre": "id", "tipo": "INTEGER" }, { "nombre": "precio", "tipo": "DECIMAL" } ],
  "muestra": ResultadoSQL }   // primeras 5 filas
```

- `cuerpo_md`, `enunciado_md`, `nota` y `tip` son texto (los `_md` en Markdown).
- El `tipo` de las columnas es el que se **muestra** al estudiante (`INTEGER`, `TEXT`, `DECIMAL`, `DATE`); el archivo `.sqlite` usa `REAL` y `TEXT`.
- Los resultados se calculan en el seed con SQLite, el mismo motor que sql.js en el navegador.

## `GET /api/lecciones/modulos`

Módulos ordenados por `orden`, cada uno con sus lecciones ordenadas por `orden`. `200`:

```json
[
  { "slug": "basico", "nombre": "Básico", "descripcion": "Lee y filtra datos...", "orden": 1,
    "lecciones": [
      { "slug": "select-from", "orden": 1, "titulo": "Tu primera consulta: SELECT y FROM",
        "resumen": "Lee datos de una tabla...", "duracion_min": 10, "dataset": "bodega",
        "tags": ["select", "from"],
        "ejercicios": [ { "id": "select-from-1", "orden": 1 }, { "id": "select-from-2", "orden": 2 } ] }
    ] }
]
```

Con la base vacía devuelve `[]`.

## `GET /api/lecciones/lecciones/{slug}`

`200`:

```json
{ "slug": "where", "orden": 2, "titulo": "Filtrar filas con WHERE", "resumen": "...", "duracion_min": 12,
  "modulo": { "slug": "basico", "nombre": "Básico" }, "dataset": "bodega",
  "tags": ["where"], "aprenderas": ["Filtrar filas con WHERE", "..."],
  "secciones": [ "Seccion", "..." ],
  "ejercicios": [ { "id": "where-1", "orden": 1 }, { "id": "where-2", "orden": 2 } ],
  "anterior": "select-from", "siguiente": "order-limit" }
```

- `anterior` es `null` en la primera lección y `siguiente` en la última.
- `404 LECCION_NO_EXISTE`.

## `GET /api/lecciones/ejercicios/{id}`

El `id` es `<slug de la lección>-<n>` (por ejemplo `where-2`). `200`:

```json
{ "id": "where-1", "leccion_slug": "where", "orden": 1, "total_en_leccion": 2,
  "enunciado_md": "Muestra el **nombre** y el **precio** de los productos de la categoría **Bebidas**.",
  "dataset": "bodega", "ordenado": false,
  "resultado_esperado": { "columnas": ["nombre", "precio"], "filas": [["Inca Kola 500 ml", 3.5]] } }
```

- `ordenado: true` significa que el orden de las filas importa al comparar el resultado del estudiante con `resultado_esperado`.
- **No incluye la solución.** `404 EJERCICIO_NO_EXISTE`.

## `GET /api/lecciones/datasets/{slug}`

`200`:

```json
{ "slug": "bodega", "nombre": "Bodega Doña Rosa", "lugar": "Surquillo, Lima", "descripcion": "...", "icono": "store",
  "archivo_url": "/api/lecciones/datasets/bodega/archivo", "archivo_sha256": "…",
  "tablas": [ "DatasetTabla", "..." ] }
```

`icono` es `store`, `bike` o `megaphone`. Las tablas salen en el orden en que se muestran. `404 DATASET_NO_EXISTE`.

## `GET /api/lecciones/datasets/{slug}/archivo`

Devuelve los bytes del archivo SQLite del dataset (el mismo que se carga en sql.js).

| Header | Valor |
|---|---|
| `Content-Type` | `application/vnd.sqlite3` |
| `Cache-Control` | `public, max-age=3600` |
| `ETag` | `"<archivo_sha256>"` (con comillas) |

- **`304 Not Modified`** (sin cuerpo, con `ETag` y `Cache-Control`) si `If-None-Match` coincide con el ETag. Acepta la forma débil `W/"..."`, listas separadas por comas y `*`.
- `200` en cualquier otro caso. El ETag es el sha256 de los bytes, así que cambia solo si cambia el dataset.
- `404 DATASET_NO_EXISTE`.

## `GET /interno/estructura`

**Solo red interna** (red de Docker o localhost): no tiene prefijo `/api`, no aparece en el OpenAPI y **nginx no la expone**. Su consumidor es `consultaya-progreso`, que la usa para saber qué lecciones y ejercicios existen. `200`:

```json
{ "version": "<sha256 de la estructura serializada>",
  "modulos": [
    { "slug": "basico", "nombre": "Básico", "orden": 1,
      "lecciones": [ { "slug": "select-from", "orden": 1, "ejercicios": ["select-from-1", "select-from-2"] } ] } ] }
```

- Módulos y lecciones ordenados por `orden`; ejercicios por su `orden` dentro de la lección.
- `version` es el SHA-256 (hex) del JSON de `modulos` en forma canónica: claves ordenadas, separadores `,` y `:` sin espacios, UTF-8 sin escapar. Cambia solo si cambian módulos, lecciones o ejercicios; quien la consume puede tratarla como un valor opaco.
