# OpenUTM Verification Toolkit v0.2.0

A repository to host verification tools for Flight Blender and OpenUTM products.

## Overview

This toolkit provides a configuration-driven framework for running automated
conformance and integration test scenarios against a Flight Blender instance.
It can be run as a local CLI, as a single-image Docker GUI, or in Kubernetes.

### Key Features

* **Automated Test Scenarios**: Pre-built scenarios for testing Flight Blender conformance and integration
* **Automatic Cleanup**: Scenarios automatically clean up created resources (flight declarations) after execution
* **Multiple Authentication Methods**: Support for dummy authentication (development) and OAuth2/Passport (production)
* **Comprehensive Reporting**: Generate JSON, HTML, and log reports with detailed execution results
* **Single Docker Image**: Backend (FastAPI on `:8989`) and built frontend bundled in one container
* **Live Data Integration**: Support for OpenSky Network live flight data in test scenarios
* **Configuration-Driven**: YAML-based configuration for easy customization and environment management

## Documentation

For detailed information about the verification scenarios, please refer to the
[Scenario Documentation](docs/index.md). For the GUI quick-start, see
[GUI_QUICKSTART.md](GUI_QUICKSTART.md). For Kubernetes, see
[k8s-deployment.yaml](k8s-deployment.yaml) and
[docs/deployment-guide.md](docs/deployment-guide.md).

## Quick Start

### Prerequisites

* Docker and Docker Compose (for the GUI image)
* Python 3.12 + [uv](https://docs.astral.sh/uv/) (for local CLI / dev)
* Node.js LTS (for the web editor in dev mode)

### Run the GUI in Docker (recommended)

```bash
cp .env.example .env       # optional — edit FLIGHT_BLENDER_URL etc.
make gui                   # docker compose up --build
# open http://localhost:8989
```

Stop with `make gui-stop` (`docker compose down`).

The image is built from the single `Dockerfile` (multi-stage: Vite build →
`uv` install → minimal Python runtime). `docker-compose.yml` mounts
`./config`, `./reports`, and `./scenarios` so edits and reports persist on the
host.

### Run the CLI locally

```bash
make install               # uv sync --dev -U
make run                   # ./verify.sh — runs scenarios from config/default.yaml
```

### Run scenarios end-to-end without Docker or the GUI

This is the same flow CI uses (see [.github/workflows/main.yml](.github/workflows/main.yml)):
spin up Flight Blender + dependencies via the test compose file, then run the
verification CLI against it.

```bash
# 1. Install dependencies (one-off)
uv sync --locked --all-extras --dev

# 2. Start Flight Blender and its dependencies (Postgres, Redis, RabbitMQ, …)
#    The test compose file lives under tests/.
docker compose --env-file tests/.env.tests -f tests/docker-compose.fb.yml up -d --wait

# 3. Run the PR scenario suite against it (writes reports/ on success or failure)
uv run openutm-verify --debug --config config/pull_request.yaml

# 4. Tear down when done
docker compose --env-file tests/.env.tests -f tests/docker-compose.fb.yml down
```

What the flags do:

* `--debug` — verbose logging (DEBUG level) to stdout and `reports/<run>/report.log`.
* `--config <path>` — pick the config file. Built-in options:
  * [config/default.yaml](config/default.yaml) — full daily-conformance suite.
  * [config/pull_request.yaml](config/pull_request.yaml) — fast PR smoke
    suite (the seven scenarios CI runs).
  * Drop your own under `config/local/` and point `--config` at it.

Reports land in `reports/<timestamp>/` (`report.json`, `report.html`,
`report.log`, plus per-scenario artefacts). Open the HTML report in a browser
to inspect results.

If Flight Blender is already running elsewhere (e.g. on `:8000` natively),
skip steps 2 and 4 and just point the config at it via
`flight_blender.url` or `FLIGHT_BLENDER_URL=...`.

### Local development (no Docker)

Run the backend and Vite dev server in two terminals:

```bash
make dev-backend           # uvicorn --reload on :8989
make dev-frontend          # Vite on :5173, proxies API calls to :8989
```

Edit `src/` → backend reloads. Edit `web-editor/src/` → browser reloads.

### Run the test suite

```bash
make test                  # uv run pytest tests/
```

## Configuration

The single source of truth is `config/default.yaml`. Override the path with
the `OPENUTM_CONFIG_PATH` env var.

Three ways to change config at runtime:

1. **In-app Settings screen** (recommended) — edit values, click *Save & Apply*.
   The backend writes back to the YAML (preserving comments via `ruamel.yaml`)
   and hot-reloads.
2. **Edit `config/default.yaml` directly** then click *Reload* in the Settings
   screen, or restart the container.
3. **Environment variable** at start time, e.g.
   `FLIGHT_BLENDER_URL=http://my-blender:8000 make gui`.

### Authentication

`flight_blender.auth` supports `type: none` (dummy auth, default) and
`type: passport` (OAuth2). For Passport, set `client_id`, `client_secret`,
`token_endpoint`, `passport_base_url`, `audience`, and `scopes`.

### Scenario data

Scenarios are driven by config, which references files used to generate flight
declarations and telemetry in memory:

```yaml
data_files:
  trajectory: "config/bern/trajectory_f1.json"
  flight_declaration: "config/bern/flight_declaration.json"

suites:
  basic_conformance:
    scenarios:
      - name: F1_happy_path
        trajectory: "config/bern/trajectory_f1.json"   # optional override
```

## Web UI (Scenario Editor)

The web editor lives in [web-editor](web-editor) (React + Vite + `@xyflow/react`).
It is built into the Docker image automatically. To work on it locally, see
**Local development** above, or build standalone:

```bash
cd web-editor
npm install
npm run build              # outputs to web-editor/dist
```

## Version Management

This project uses `uv` for dependency management. Bump the version with:

```bash
uv version bump --patch    # 1.0.0 → 1.0.1
uv version bump --minor    # 1.0.0 → 1.1.0
uv version bump --major    # 1.0.0 → 2.0.0
uv version bump 1.2.3      # explicit
uv version bump --patch --dry-run
```

This updates the `version` field in `pyproject.toml`.

## Maintenance

```bash
docker compose ps                    # container status
docker compose logs -f verification  # follow logs
docker compose exec verification sh  # shell into the container
docker compose down -v               # stop and remove volumes
make clean                           # local artefacts (caches, reports/*)
```

### Troubleshooting

* **Port 8989 already in use** — `lsof -i :8989`, then stop the offender.
* **Permission denied on `./reports`** — `sudo chown -R 1000:1000 ./reports`.
* **Backend can't reach Flight Blender from container** — set
  `FLIGHT_BLENDER_URL=http://host.docker.internal:8000` (macOS/Windows) or
  the appropriate URL for your network.
* **Settings *Save & Apply* fails read-only** — confirm `./config` mount in
  `docker-compose.yml` is `:rw`.

## Configuration Files

* `Dockerfile` — single multi-stage build (Vite UI + Python backend)
* `docker-compose.yml` — single service definition for local Docker use
* `k8s-deployment.yaml` — example Kubernetes manifests
* `.env.example` — environment variables template
* `config/default.yaml` — default app configuration
