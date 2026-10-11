FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    RUFF_CACHE_DIR=/tmp/ruff-cache

WORKDIR /workspace/backend
COPY pyproject.toml ./
COPY app ./app
RUN python -m pip install --no-cache-dir '.[dev]' \
    && useradd --uid 10001 --create-home app
COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests

USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
