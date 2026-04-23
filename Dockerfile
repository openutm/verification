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

# Install build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Configure UV
ENV UV_COMPILE_BYTECODE=${UV_COMPILE_BYTECODE}
ENV UV_LINK_MODE=${UV_LINK_MODE}
ENV PYTHONUNBUFFERED=1

# Install dependencies first for better caching
COPY pyproject.toml uv.lock ./
COPY docs ./docs
COPY scenarios ./scenarios

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy application source and install
COPY LICENSE README.md ./
COPY src ./src
COPY tests ./tests

RUN uv pip install --no-deps . && rm -f LICENSE

# --- Production Runtime Stage ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS production

ARG APP_USER=appuser
ARG APP_GROUP=appgrp
ARG UID=1000
ARG GID=1000

# Install minimal runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Configure environment for GUI server mode
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC
ENV PATH="/app/.venv/bin:$PATH"
ENV WEB_EDITOR_PATH=/app/web-editor
ENV SCENARIOS_PATH=/app/scenarios
ENV DOCS_PATH=/app/docs
# Configuration and reports paths (typically mounted as volumes)
ENV OPENUTM_CONFIG_PATH=config/default.yaml
ENV REPORTS_DIR=reports

# Create non-root user
RUN (getent group "${GID}" || groupadd -g "${GID}" "${APP_GROUP}") \
    && useradd -u "${UID}" -g "${GID}" -s /bin/sh -m "${APP_USER}"

# Copy application from builder
COPY --chown=${UID}:${GID} --from=builder /app /app

# Copy built UI from ui-builder
COPY --chown=${UID}:${GID} --from=ui-builder /app/web-editor/dist /app/web-editor/dist

WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/config /app/reports \
    && chown -R ${UID}:${GID} /app/config /app/reports

USER ${UID}:${GID}

# Expose the server port (backend serves both API and frontend)
EXPOSE 8989

# Health check for the API
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8989/health || exit 1

# Start the server in GUI mode
# The backend serves the built frontend at / (via StaticFiles mount) and API at:
#   - /health, /operations, /session/*, /run-scenario*, /stop-scenario
#   - /reports (static mounted directory for report access)
#
# Environment variables:
#   OPENUTM_CONFIG_PATH: Path to YAML config (default: config/default.yaml)
#   FLIGHT_BLENDER_URL: Override Flight Blender endpoint
#   LOG_LEVEL: Logging verbosity (DEBUG, INFO, WARNING, ERROR)
ENTRYPOINT ["python", "-m", "uvicorn", "openutm_verification.server.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8989"]
