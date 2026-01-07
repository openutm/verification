# --- UI Builder Stage ---
FROM node:20-slim AS ui-builder
WORKDIR /app/web-editor
COPY web-editor/package.json web-editor/package-lock.json ./
RUN npm ci
COPY web-editor/ .
RUN npm run build

# --- Builder Stage ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Build arguments
ARG UV_COMPILE_BYTECODE=1
ARG UV_LINK_MODE=copy

# Install necessary build-time dependencies for compiling Python extensions
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory for the application in the builder image
WORKDIR /app

# Configure UV for optimal Docker layer caching and performance
ENV UV_COMPILE_BYTECODE=${UV_COMPILE_BYTECODE}
ENV UV_LINK_MODE=${UV_LINK_MODE}
ENV PYTHONUNBUFFERED=1

# --- Dependency Installation Layer ---
# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./
COPY docs ./docs
COPY scenarios ./scenarios

# Install project dependencies using uv sync with cache mount for faster builds
# --frozen: ensures reproducible builds from uv.lock
# --no-install-project: skips installing the project itself (we do this later)
# --no-dev: excludes development dependencies for production builds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# --- Application Installation Layer ---
# Copy the rest of the application source code
COPY LICENSE README.md ./
COPY src ./src
COPY tests ./tests

# Install the project itself in the builder stage
# --no-deps: Dependencies are already installed, skip resolution
RUN uv pip install --no-deps . && rm -f LICENSE

# --- Production Stage ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS production

# Build arguments for production stage
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

# Configure environment
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC
ENV PATH="/app/.venv/bin:$PATH"
ENV WEB_EDITOR_PATH=/app/web-editor
ENV SCENARIOS_PATH=/app/scenarios

# Create non-root user and group for enhanced security
RUN (getent group "${GID}" || groupadd -g "${GID}" "${APP_GROUP}") \
    && useradd -u "${UID}" -g "${GID}" -s /bin/sh -m "${APP_USER}"

# Copy application artifacts from builder stage
COPY --chown=${UID}:${GID} --from=builder /app /app

# Copy UI artifacts from ui-builder stage
COPY --chown=${UID}:${GID} --from=ui-builder /app/web-editor/dist /app/web-editor/dist

# Set working directory
WORKDIR /app

# Create necessary directories with proper permissions
RUN mkdir -p /app/config /app/reports \
    && chown -R ${UID}:${GID} /app/config /app/reports

# Switch to non-root user
USER ${UID}:${GID}

# Expose the server port
EXPOSE 8989

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; print('OK'); sys.exit(0)" || exit 1

# Define the entrypoint for the container
ENTRYPOINT ["openutm-verify"]

# Set the default command with arguments
CMD ["--config", "config/default.yaml"]
