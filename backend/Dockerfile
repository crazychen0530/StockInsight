FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    RUFF_CACHE_DIR=/tmp/ruff-cache

WORKDIR /workspace/backend
COPY pyproject.toml ./
COPY constraints.txt ./
COPY app ./app
ARG INSTALL_EXTRAS=dev
RUN --mount=type=secret,id=build_proxy \
    if [ -f /run/secrets/build_proxy ]; then export HTTPS_PROXY="$(cat /run/secrets/build_proxy)"; fi; \
    python -m pip install --no-cache-dir -c constraints.txt ".[${INSTALL_EXTRAS}]" \
    && useradd --uid 10001 --create-home app
COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests

USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
