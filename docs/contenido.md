# Contenido (datasets, lecciones y ejercicios) y seed

El contenido del curso vive **como código** en `contenido/` y se carga a Postgres con `scripts/seed.py`. No hay panel de administración: para cambiar una lección se edita un archivo, se corre el seed y listo.

## Estructura de `contenido/`

```
contenido/
├── modulos.yaml
├── datasets/
│   ├── bodega.yaml        metadatos, tipos para mostrar y descripción de tablas
│   ├── bodega.sql         CREATE TABLE + INSERT (fuente de verdad de los datos)
│   ├── delivery.yaml / delivery.sql
│   └── campanas.yaml / campanas.sql
└── lecciones/
    ├── 01-select-from.yaml
    ├── 02-where.yaml
    ├── 03-order-limit.yaml
    ├── 04-filtros.yaml
    ├── 05-agregacion.yaml
    ├── 06-group-by.yaml
    ├── 07-join.yaml
    └── 08-metricas.yaml
```

Hoy son 3 módulos (Básico, Intermedio, Avanzado), 3 datasets, 8 lecciones y 16 ejercicios (Básico 6, Intermedio 6, Avanzado 4).

Los archivos se leen en UTF-8 (se tolera un BOM) y los saltos de línea CRLF se normalizan a LF al leer: el resultado y el `sha256` de cada dataset son iguales en macOS, Linux y Windows. El repo fuerza LF con `.gitattributes`.

## Formatos

### `modulos.yaml`

```yaml
- slug: basico
  nombre: Básico
  orden: 1
  descripcion: "Lee y filtra datos de una tabla: SELECT, WHERE, ORDER BY y LIMIT."
```

### `datasets/<slug>.yaml`

```yaml
slug: bodega
nombre: Bodega Doña Rosa
lugar: Surquillo, Lima
icono: store                  # store | bike | megaphone (lo usa el frontend)
descripcion: Productos, clientes y ventas diarias de una bodega de barrio.
tablas:                       # en el orden en que se muestran
  - nombre: productos
    descripcion: Catálogo de productos con su precio (S/) y unidades en stock.
    columnas:                 # tipo que se MUESTRA al estudiante
      - { nombre: id, tipo: INTEGER }
      - { nombre: nombre, tipo: TEXT }
      - { nombre: precio, tipo: DECIMAL }
```

### `datasets/<slug>.sql`

```sql
CREATE TABLE productos (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, categoria TEXT NOT NULL, precio REAL NOT NULL, stock INTEGER NOT NULL);
INSERT INTO productos VALUES (1, 'Inca Kola 500 ml', 'Bebidas', 3.50, 48);
INSERT INTO productos VALUES (11, 'Papitas Lay''s', 'Snacks', 2.50, 30);
```

Reglas:

- **Tipos SQLite:** `DECIMAL` se escribe `REAL`; `DATE` se escribe `TEXT` con formato `'YYYY-MM-DD'`; `INTEGER` y `TEXT` igual. En el YAML se conserva el tipo que se muestra (`DECIMAL`, `DATE`).
- **Comillas:** los textos van entre comillas simples; una comilla dentro del texto se duplica (`'Papitas Lay''s'`).
- **Sin tildes ni ñ en nombres de tablas y columnas** (la tabla del dataset de campañas se llama `campanas`). Los valores de texto sí pueden llevarlos.
- Las columnas del YAML deben coincidir, en nombre y orden, con las de la tabla real, y las tablas del YAML con las del `.sql`.

### `lecciones/NN-<slug>.yaml`

```yaml
slug: where
modulo: basico
orden: 2
dataset: bodega
duracion_min: 12
titulo: Filtrar filas con WHERE
resumen: Quédate solo con las filas que cumplen una condición.
tags: [where, filtrar, condicion, comparar]
aprenderas:
  - Filtrar filas con WHERE
  - Comparar números con >, <, >= y <=
secciones:
  - titulo: La cláusula WHERE
    cuerpo_md: |
      Muchas veces no necesitas todas las filas. `WHERE` va después de `FROM` e indica una condición.
    ejemplo:                  # opcional (null si la sección no lleva ejemplo)
      sql: |
        SELECT nombre, distrito
        FROM clientes
        WHERE distrito = 'Surquillo';
      nota: Los textos van entre comillas simples y deben escribirse igual que en la tabla.
    tip: null                 # opcional
ejercicios:
  - enunciado_md: Muestra el **nombre** y el **precio** de los productos de la categoría **Bebidas**.
    solucion_sql: SELECT nombre, precio FROM productos WHERE categoria = 'Bebidas'
    ordenado: false           # true si el orden de las filas importa
```

- El `slug` de la lección es su identificador (minúsculas, números y guiones) y el nombre del archivo es solo una ayuda para ordenar la carpeta; el orden real es `orden` (global, 1..N, sin repetir).
- El id de cada ejercicio es `<slug>-<n>`, con `n` desde 1 según su posición en `ejercicios`. **No reordenes ni borres ejercicios ya publicados** sin pensar en el avance guardado de los estudiantes (el servicio de progreso los referencia por id).
- Texto de estudiante en español peruano, con tuteo ("Escribe tu consulta", "Muestra el nombre…"), soles como `S/`.
- `cuerpo_md`, `enunciado_md`, `nota` y `tip` admiten Markdown (`**negrita**`, `*cursiva*`, `` `código` ``, párrafos y tablas).

## Cómo agregar contenido

**Una lección nueva**

1. Crea `contenido/lecciones/NN-<slug>.yaml` con el formato de arriba (elige un `orden` libre, o reordena las demás).
2. Asegúrate de que el `modulo` y el `dataset` existan.
3. Incluye al menos una sección con `ejemplo` y al menos un ejercicio.
4. Corre `uv run python scripts/seed.py` y revisa el resumen.
5. Ajusta los tests que cuentan el contenido (`tests/test_seed.py`, `tests/test_api.py`) y agrega los resultados esperados de tus ejercicios.

**Un ejercicio nuevo:** agrégalo al final de `ejercicios` de la lección (así los ids existentes no cambian) y vuelve a sembrar.

**Un dataset nuevo:** crea `datasets/<slug>.sql` y `datasets/<slug>.yaml` (ver reglas arriba) y úsalo desde las lecciones.

**Un módulo nuevo:** agrégalo a `modulos.yaml` con un `orden` único.

## Qué hace el seed (`scripts/seed.py`)

Uso: `uv run python scripts/seed.py [--contenido RUTA]` (lee `DATABASE_URL`).

1. **Valida** los YAML: campos obligatorios y sin campos desconocidos, slugs válidos y únicos, `orden` únicos (módulos y lecciones), cada lección apunta a un módulo y a un dataset existentes, al menos una sección con `ejemplo` y al menos un ejercicio por lección.
2. **Construye cada dataset:** crea un SQLite en memoria, ejecuta el `.sql`, valida que tablas y columnas coincidan con el YAML, serializa la base a bytes (ese es el archivo que se sirve), calcula su `sha256` y arma `tablas` (columnas del YAML, `filas_total` y `muestra` con las primeras 5 filas).
3. **Ejecuta cada `ejemplo.sql`** de las lecciones sobre su dataset y guarda el `resultado`.
4. **Ejecuta cada `solucion_sql`** y guarda el `resultado_esperado`. Las consultas corren en modo solo lectura.
5. **Escribe en Postgres** en **una sola transacción**: upsert por slug o id y borrado de lo que ya no existe en `contenido/`. Se puede reordenar lecciones sin choques de `orden`.
6. Imprime el resumen: `3 módulos · 3 datasets · 8 lecciones · 16 ejercicios`.

Ante cualquier error (YAML inválido, SQL que falla, columnas que no coinciden…) sale con código 1 y un mensaje claro (lección, sección o ejercicio, y el error de SQLite), **sin escribir nada** en la base. Es **idempotente**: correrlo de nuevo no duplica nada.

`ResultadoSQL` es `{"columnas": [...], "filas": [[...], ...]}` con los valores tal como los devuelve `sqlite3` (int, float, str, null). Como sql.js es SQLite, el resultado esperado coincide con lo que obtiene el estudiante en el navegador. La solución (`solucion_sql`) se guarda en la base pero **nunca** sale por la API.

## Resultados esperados (los verifican los tests del seed)

| Ejercicio | Filas × columnas | Ordenado | Verificación |
|---|---|---|---|
| select-from-1 | 12 × 5 | no | todas las columnas de `productos` |
| select-from-2 | 12 × 2 | no | `nombre, precio` |
| where-1 | 3 × 2 | no | Inca Kola, Coca-Cola, Agua San Luis |
| where-2 | 3 × 2 | no | Aceite Primor 18, Yogurt Laive 15, Detergente Bolívar 12 |
| order-limit-1 | 3 × 2 | sí | Aceite Primor 11.5 → Detergente 8.9 → Coca-Cola 7.0 |
| order-limit-2 | 6 × 1 | sí | Carlos Rojas → … → Rosa Mamani |
| filtros-1 | 8 × 3 | no | ids 2, 3, 6, 7, 9, 12, 13, 16 |
| filtros-2 | 2 × 2 | no | Cevichería La Chalaca, Sanguchería Don Lucho |
| agregacion-1 | 1 × 1 | no | 12 |
| agregacion-2 | 1 × 1 | no | ≈ 708.40 |
| group-by-1 | 5 × 2 | sí | Miraflores 275.4, Lince 161.7, San Isidro 137.5, Surco 103.9, Barranco 29.9 |
| group-by-2 | 3 × 2 | no | Lince 4, Miraflores 4, Surco 3 |
| join-1 | 15 × 2 | no | una fila por venta |
| join-2 | 6 × 2 | no | Bebidas 12, Panadería 18, Lácteos 6, Abarrotes 4, Snacks 6, Limpieza 1 |
| metricas-1 | 8 × 2 | sí | Remarketing 6.0 primero, Regreso a clases 2.0 último |
| metricas-2 | 3 × 2 | no | Facebook 3300, Instagram 3000, Google Ads 4300 |
