# OpenUTM Verification Toolkit v0.1.2

A repository to host verification tools for Flight Blender and OpenUTM products.

## Overview

This toolkit provides a configuration-driven framework for running automated conformance and integration test scenarios against a Flight Blender instance. It is designed to be run as a standalone tool or within a Docker container.

### Key Features

* **Automated Test Scenarios**: Pre-built scenarios for testing Flight Blender conformance and integration
* **Automatic Cleanup**: Scenarios automatically clean up created resources (flight declarations) after execution
* **Multiple Authentication Methods**: Support for dummy authentication (development) and OAuth2/Passport (production)
* **Comprehensive Reporting**: Generate JSON, HTML, and log reports with detailed execution results
* **Docker Integration**: Full containerization support for production and development environments
* **Live Data Integration**: Support for OpenSky Network live flight data in test scenarios
* **Configuration-Driven**: YAML-based configuration for easy customization and environment management

## Quick Start

### Prerequisites

* Docker
* Docker Compose

### 1. Environment Setup

Copy the environment template and customize it for your setup:

```bash
cp .env.example .env
# Edit .env with your Flight Blender URL and other settings
```

### 2. Build the Docker Images

Build the production and development images:

```bash
# Build all images (production + development)
./scripts/build.sh

# Build all images with verbose output
./scripts/build.sh -v

# Build all images with force rebuild (skip cache)
./scripts/build.sh -f

# Build only production image
./scripts/build.sh production

# Build only development image
./scripts/build.sh development
```

### 3. Run Verification Scenarios

#### Production Mode (Recommended)

**Run with default configuration:**

```bash
./scripts/run.sh
```

**Run with custom configuration:**

```bash
./scripts/run.sh --config config/custom.yaml
```

**Run with debug logging:**

```bash
./scripts/run.sh --debug
```

**Run with debug logging and production settings:**

```bash
./scripts/run.sh -p --debug
```

**Run with verbose output:**

```bash
./scripts/run.sh -v
```

**Build and run in production mode:**

```bash
./scripts/run.sh -b
```

#### Development Mode

**Run in development mode with hot reload:**

```bash
./scripts/run.sh -d
```

**Build and run in development mode:**

```bash
./scripts/run.sh -d -b
```

**Run in development mode with verbose output:**

```bash
./scripts/run.sh -d -v
```

#### Testing Mode

**Run tests in an isolated environment:**

```bash
docker compose --profile test run --rm test-runner
```

This command starts a dedicated container using the `test-runner` service definition, which is configured to execute the `pytest` suite against the codebase.

## Docker Workflow Details

### Environment Configuration

The toolkit uses environment variables for configuration. Key variables include:

* `FLIGHT_BLENDER_URL`: URL of the Flight Blender instance to test
* `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
* `ENVIRONMENT`: Environment name for labeling

#### Authentication Configuration

For authentication, the following fields can be configured in `config/default.yaml` under `flight_blender.auth`:

* `audience`: The OAuth audience for token requests. Default: "testflight.flightblender.com"
* `scopes`: The list of scopes for token requests. Default: ["flightblender.write", "flightblender.read"]

When using `type: "passport"`, also set `client_id`, `client_secret`, and `token_url` as needed.

### Docker Compose Services

#### Production Service (`verification-tool`)

* Optimized for production use
* Minimal image size with security hardening
* Volume mounts for config and reports
* Host network mode for local Flight Blender access

#### Development Service (`verification-dev`)

* Includes development tools and dependencies
* Hot reload capabilities
* Full source code mounting
* Debug logging enabled by default

#### Testing Service (`test-runner`)

* Isolated testing environment
* Runs pytest with coverage
* Separate from main application

### Build Optimization

The Docker setup includes several optimizations:

* **Multi-stage builds**: Separate builder and production stages
* **Layer caching**: Optimized for faster rebuilds
* **Security**: Non-root user, minimal attack surface
* **Performance**: UV package manager for fast Python installs

### Volume Management

The following directories are mounted as volumes:

* `./config:/app/config`: Configuration files
* `./reports:/app/reports`: Generated reports
* `./src:/app/src`: Source code (development only)

### Network Configuration

The containers use `network_mode: host` to:

* Access Flight Blender running on `localhost`
* Maintain consistent networking behavior
* Avoid port conflicts

## Advanced Usage

### Custom Build Arguments

Override build arguments for specific needs:

```bash
docker build \
  --build-arg UV_COMPILE_BYTECODE=0 \
  --build-arg APP_USER=myuser \
  --build-arg UID=1001 \
  -t custom-verification .
```

### Development Workflow

1. **Start development environment:**

   ```bash
   ./scripts/run.sh -d -b
   ```

2. **Run tests:**

   ```bash
   docker compose --profile test run --rm test-runner
   ```

3. **Check logs:**

   ```bash
   docker compose logs verification-dev
   ```

### Production Deployment

1. **Build optimized image:**

   ```bash
   ./scripts/build.sh production
   ```

2. **Build with force rebuild:**

   ```bash
   ./scripts/build.sh -f production
   ```

3. **Run with production settings:**

   ```bash
   ./scripts/run.sh -p
   ```

4. **Run with verbose output:**

   ```bash
   ./scripts/run.sh -v
   ```

## Version Management

This project uses `uv` for dependency management and version control. The `uv version bump` command allows you to easily update the project version in `pyproject.toml`.

### Basic Usage

Bump the version to the next patch version (e.g., 1.0.0 → 1.0.1):

```bash
uv version bump --patch
```

Bump the version to the next minor version (e.g., 1.0.0 → 1.1.0):

```bash
uv version bump --minor
```

Bump the version to the next major version (e.g., 1.0.0 → 2.0.0):

```bash
uv version bump --major
```

### Advanced Options

Bump to a specific version:

```bash
uv version bump 1.2.3
```

Preview the changes without applying them:

```bash
uv version bump --patch --dry-run
```

The version bump will update the `version` field in `pyproject.toml` and ensure consistency across the project.

## Maintenance

### Cleanup

Clean up Docker resources:

```bash
# Clean all project resources
./scripts/cleanup.sh -a

# Clean all resources with force (no confirmation)
./scripts/cleanup.sh -f -a

# Clean all resources with verbose output
./scripts/cleanup.sh -V -a

# Clean specific resources
./scripts/cleanup.sh -c -i
./scripts/cleanup.sh -d

# Clean containers only
./scripts/cleanup.sh -c

# Clean images only
./scripts/cleanup.sh -i

# Clean volumes only
./scripts/cleanup.sh -v

# Clean networks only
./scripts/cleanup.sh -n

# Clean dangling resources only
./scripts/cleanup.sh -d
```

### Health Checks

Monitor container health:

```bash
# Check container status
docker compose ps

# View logs
docker compose logs verification-tool

# Check health status
docker compose exec verification-tool python -c "print('OK')"
```

### Troubleshooting

**Common issues:**

1. **Permission denied**: Ensure proper file permissions on mounted volumes
2. **Network connectivity**: Verify Flight Blender is accessible on specified URL
3. **Build failures**: Check Docker daemon and available disk space

**Debug commands:**

```bash
# Enter running container
docker compose exec verification-tool bash

# View detailed logs
docker compose logs --tail=100 -f verification-tool

# Check container resource usage
docker stats
```

## Configuration Files

* `docker-compose.yml`: Main service definitions
* `docker-compose.override.yml`: Development overrides
* `Dockerfile`: Production image definition
* `Dockerfile.dev`: Development image definition
* `.dockerignore`: Files excluded from build context
* `.env.example`: Environment variables template

Reports will be generated in the `reports/` directory on your local machine.

## Script Arguments Reference

All scripts in this project follow a consistent argument structure for better usability:

### Common Flags

| Flag | Long Form | Description | Available In |
|------|-----------|-------------|--------------|
| `-h` | `--help` | Show help message | All scripts |
| `-v` | `--verbose` | Enable verbose output | All scripts |
| `-f` | `--force` | Force operation without confirmation | build.sh, cleanup.sh |

### Script-Specific Flags

#### `run.sh` - Run Verification Tool

| Flag | Long Form | Description |
|------|-----------|-------------|
| `-d` | `--dev` | Run in development mode |
| `-p` | `--production` | Run in production mode (default) |
| `-b` | `--build` | Build images before running |
| | `--clean` | Clean up after run |

#### `build.sh` - Build Docker Images

| Argument | Description |
|----------|-------------|
| `production` | Build production image only |
| `development` | Build development image only |
| `all` | Build both images (default) |

#### `cleanup.sh` - Clean Docker Resources

| Flag | Long Form | Description |
|------|-----------|-------------|
| `-a` | `--all` | Clean all resources |
| `-c` | `--containers` | Clean containers only |
| `-i` | `--images` | Clean images only |
| `-v` | `--volumes` | Clean volumes only |
| `-n` | `--networks` | Clean networks only |
| `-d` | `--dangling` | Clean dangling resources only |

### Examples

```bash
# Get help for any script
./scripts/run.sh --help
./scripts/build.sh --help
./scripts/cleanup.sh --help

# Use verbose output across all scripts
./scripts/run.sh -v
./scripts/build.sh -v production
./scripts/cleanup.sh -V -a

# Force operations where available
./scripts/build.sh -f production
./scripts/cleanup.sh -f -a
```
