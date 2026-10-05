# consultaya-lecciones

Parte de ConsultaYa (MVP para aprender SQL). Lee primero los docs de **este repo**:

- `README.md`: qué hace el servicio, cómo correrlo, testearlo y sembrar (macOS, Linux y Windows).
- `docs/api.md`: endpoints, objetos, errores, ETag/304 y la garantía de que `solucion_sql` nunca sale por la API.
- `docs/contenido.md`: formato de `contenido/`, cómo agregar lecciones y qué valida y hace el seed.

Opcional, solo si existe el workspace completo: `../docs/` (especificación del sistema, contratos de API entre servicios y convenciones generales).

- Rol de este repo: microservicio de lecciones (módulos, lecciones, ejercicios, datasets, contenido y seed).
- No cambiar endpoints ni formatos sin aprobación (`docs/api.md` es el contrato que consumen `progreso` y el frontend).
- Puerto local: 8002 (8000 en Docker) · Bases: `consultaya_lecciones`, `consultaya_lecciones_test`.
- Reglas duras: solo bases `consultaya_*`; nunca commitear `.env` ni datos de tu máquina (usuarios, rutas absolutas); sin líneas Co-Authored-By; commits en Conventional Commits en español.
