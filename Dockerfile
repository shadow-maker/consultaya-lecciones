FROM python:3.12-slim

# Binario de uv (versión fijada).
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencias primero (capa cacheable).
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY scripts/ scripts/
COPY contenido/ contenido/

RUN useradd --system --uid 10001 --no-create-home app && chown -R app:app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
