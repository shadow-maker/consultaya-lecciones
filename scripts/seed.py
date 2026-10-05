"""Siembra el contenido de `contenido/` en la base (`DATABASE_URL`). Idempotente.

Uso:  uv run python scripts/seed.py [--contenido RUTA]

Valida el contenido, construye cada dataset con SQLite, ejecuta ejemplos y soluciones, y escribe
todo en una sola transacción. Ante cualquier error sale con código 1 sin haber escrito nada.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # permite `import app`

from app.contenido import RAIZ_CONTENIDO, ContenidoError, cargar_y_construir  # noqa: E402
from app.db import engine  # noqa: E402
from app.sembrar import sembrar  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Siembra el contenido de ConsultaYa · lecciones.")
    parser.add_argument("--contenido", type=Path, default=RAIZ_CONTENIDO, help="carpeta contenido/")
    args = parser.parse_args(argv)
    try:
        datos = cargar_y_construir(args.contenido)
    except ContenidoError as exc:
        print(f"Error en el contenido: {exc}\nNo se escribió nada en la base.", file=sys.stderr)
        return 1
    sembrar(engine, datos)
    print(datos.resumen())
    return 0


if __name__ == "__main__":
    # La consola de Windows puede no ser UTF-8 (el resumen lleva tildes y "·").
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8")
    raise SystemExit(main())
