# --- Builder Stage ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# Install necessary build-time dependencies for compiling Python extensions and other tools.
RUN apt-get -y update \
    && apt-get install -y --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory for the application in the builder image.
WORKDIR /app

# Enable bytecode compilation for performance in production.
ENV UV_COMPILE_BYTECODE=1

# Ensure unbuffered Python output for immediate logging in container environments.
ENV PYTHONUNBUFFERED=1

# Copy from the cache instead of linking. This is safer for potential volume mount scenarios
# in development/CI and ensures consistent behavior in production builds.
ENV UV_LINK_MODE=copy

# --- Dependency Installation Layer ---
# Copy only the lockfile and pyproject.toml to leverage Docker layer caching.
# This ensures dependencies are re-installed only when these files change.
COPY uv.lock pyproject.toml ./

# Install project dependencies using uv sync with a cache mount for faster builds.
# --frozen: ensures reproducible builds from uv.lock
# --no-install-project: skips installing the project itself (we do this later)
# --no-dev: excludes development dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# --- Application Installation Layer ---
# Copy the rest of the application source code.
COPY README.md LICENSE run_verification.py ./
COPY pyproject.toml ./
COPY src ./src
COPY tests ./tests

# Install the project itself in the builder stage after copying source code.
# --no-deps:  Dependencies are already installed in the previous step, so skip dependency resolution.
RUN uv pip install --no-deps . && rm -f README.md

# --- Production Stage ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim


# Ensure unbuffered Python output for immediate logging in container environments.
ENV PYTHONUNBUFFERED=1

# Install runtime dependencies required for the application to run.
# In this case, only libpq5 is needed for PostgreSQL runtime connectivity.
RUN apt-get -y update \
    && apt-get install -y --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --- Security: Create a non-root user and group for enhanced security ---
ENV APP_USER=appuser
ENV APP_GROUP=appgrp
ENV UID=1000
ENV GID=1000
RUN groupadd -g "$GID" "$APP_GROUP" && useradd -u "$UID" -g "$APP_GROUP" -s /bin/sh "$APP_USER"

# Copy application artifacts from the builder stage to the production image.
# --chown ensures the files are owned by the non-root user and group.
COPY --chown=$APP_USER:$APP_GROUP --from=builder /app /app

# Set working directory in the production image.
WORKDIR /app

# Set executable path to include the virtual environment's bin directory.
ENV PATH="/app/.venv/bin:$PATH"

# Set timezone to UTC for consistent timekeeping across environments.
ENV TZ=UTC


# --- Switch to the non-root user for running the application ---
USER $APP_USER:$APP_GROUP

# Define the entrypoint for the container
ENTRYPOINT ["python", "run_verification.py"]

# Set the default command with arguments for the entrypoint
CMD ["--config", "config/default.yaml"]
