# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Build the project wheel for its metadata only. The runtime runs the code from
# /app, but `aegis doctor` needs the distribution metadata to print its version.
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv build --wheel --out-dir /dist \
    && uv pip install --no-deps --target /meta /dist/*.whl \
    && mkdir /distinfo \
    && mv /meta/aegis-*.dist-info /distinfo/

FROM python:3.12-slim-bookworm AS mock

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY scripts ./scripts

RUN groupadd --system aegis \
    && useradd --system --gid aegis --create-home aegis \
    && chown -R aegis:aegis /app

USER aegis

EXPOSE 9000

HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=20 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9000/_tap', timeout=3)"

CMD ["uvicorn", "scripts.mock_upstream:app", "--host", "0.0.0.0", "--port", "9000"]

FROM python:3.12-slim-bookworm AS runtime

# CPU-only torch wheels need the GNU OpenMP runtime; no CUDA libraries are installed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/aegis \
    HF_HOME=/home/aegis/.cache/huggingface

WORKDIR /app
COPY app ./app
COPY data ./data
COPY scripts ./scripts

# Bake the configured GLiNER model into the image and prove it can warm.
# The offline flags below make the runtime depend only on this build-time cache.
RUN python -c "from app.scrubber.ner import get_ner; get_ner().warm()"

# Metadata only: the code itself stays at /app. This keeps the model layer above
# cached when the project version changes.
COPY --from=builder /distinfo /opt/venv/lib/python3.12/site-packages/

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

RUN groupadd --system aegis \
    && useradd --system --gid aegis --no-create-home aegis \
    && printf '#!/bin/sh\nexec python -m app.cli "$@"\n' > /usr/local/bin/aegis \
    && chmod 0755 /usr/local/bin/aegis \
    && chown -R aegis:aegis /home/aegis /app

USER aegis

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
