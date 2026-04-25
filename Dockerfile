# Multi-stage Dockerfile for OpenUTM Verification
# Single image: FastAPI backend on :8989 also serves the built React frontend.
#
# For local development, skip Docker and run two processes directly:
#   1. uv run uvicorn openutm_verification.server.main:app --reload --port 8989
#   2. cd web-editor && npm run dev   # Vite on :5173, proxies API to :8989

# --- UI Builder Stage ---
FROM node:25-slim AS ui-builder
WORKDIR /app/web-editor

# Install dependencies first for better layer caching
COPY web-editor/package.json web-editor/package-lock.json ./
RUN npm ci

# Copy source and build
COPY web-editor/ .
RUN npm run build

# --- Backend Builder Stage ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ARG UV_COMPILE_BYTECODE=1
ARG UV_LINK_MODE=copy

# `git` is required because one dependency (`cam-track-gen`) is fetched from
# a Git repo (see `pyproject.toml`); uv shells out to the `git` CLI to clone
# it. All other dependencies resolve to prebuilt wheels, so no C toolchain
# is needed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_COMPILE_BYTECODE=${UV_COMPILE_BYTECODE} \
    UV_LINK_MODE=${UV_LINK_MODE} \
    PYTHONUNBUFFERED=1

# Resolve dependencies first (cached unless lockfile changes).
# `docs/scenarios` is force-included into the wheel by hatch, so the docs
# tree must be present at build time.
COPY pyproject.toml uv.lock ./
COPY docs ./docs
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Build & install just the project wheel (no editable, no tests).
COPY LICENSE README.md ./
COPY src ./src
RUN uv pip install --no-deps .

# --- Production Runtime Stage ---
# Plain python image — `uv` is only needed at build time, so dropping it
# from the runtime keeps the final image smaller.
FROM python:3.12-slim-bookworm AS production

ARG APP_USER=appuser
ARG APP_GROUP=appgrp
ARG UID=1000
ARG GID=1000

# No extra runtime apt packages — Python's stdlib covers the healthcheck,
# and `tzdata` ships with the Python image.

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC \
    PATH="/app/.venv/bin:$PATH" \
    WEB_EDITOR_PATH=/app/web-editor \
    SCENARIOS_PATH=/app/scenarios \
    DOCS_PATH=/app/docs \
    OPENUTM_CONFIG_PATH=config/default.yaml \
    REPORTS_DIR=reports

# Non-root user
RUN (getent group "${GID}" || groupadd -g "${GID}" "${APP_GROUP}") \
    && useradd -u "${UID}" -g "${GID}" -s /bin/sh -m "${APP_USER}"

WORKDIR /app

# Copy only what's needed at runtime: the venv (project + deps installed,
# including the package's bundled `assets/` data files), the docs/scenarios
# trees used as defaults, and the built UI bundle. The `src/` tree is NOT
# copied — the wheel installed into the venv contains everything the app
# imports, and sample data files live under `config/` (bind-mounted).
COPY --chown=${UID}:${GID} --from=builder /app/.venv /app/.venv
COPY --chown=${UID}:${GID} docs /app/docs
COPY --chown=${UID}:${GID} scenarios /app/scenarios
COPY --chown=${UID}:${GID} --from=ui-builder /app/web-editor/dist /app/web-editor/dist

# Volume targets (config + reports are normally bind-mounted in compose).
RUN mkdir -p /app/config /app/reports \
    && chown -R ${UID}:${GID} /app/config /app/reports

USER ${UID}:${GID}

EXPOSE 8989

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8989/health', timeout=5).status == 200 else 1)" || exit 1

# Backend serves both API and frontend (StaticFiles mount at /).
# Honored env vars:
#   OPENUTM_CONFIG_PATH, FLIGHT_BLENDER_URL, LOG_LEVEL
ENTRYPOINT ["python", "-m", "uvicorn", "openutm_verification.server.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8989"]
