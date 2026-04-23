# GUI Mode Quick Start

Run the OpenUTM Verification tool with a web-based UI.

## TL;DR

```bash
make gui          # Single-image Docker GUI on http://localhost:8989
make gui-stop     # Stop the container

# For active development on the UI / backend (no Docker, two terminals):
make dev-backend  # uvicorn --reload on :8989
make dev-frontend # Vite on :5173, proxies API to :8989
```

## Setup

### Prerequisites

- Docker & Docker Compose (for `make gui`)
- Python 3.12 + [uv](https://docs.astral.sh/uv/) and Node.js LTS (for the
  local dev workflow)
- 1+ GB free disk for reports

### Optional: `.env`

```bash
cp .env.example .env
# Edit FLIGHT_BLENDER_URL, LOG_LEVEL, OPENUTM_CONFIG_PATH, etc.
docker compose --env-file .env up --build
```

## Docker (single image)

`docker-compose.yml` defines one service (`verification`) built from the
single `Dockerfile`. The backend serves both the FastAPI API and the built
React frontend on `:8989`.

```bash
make gui
# or: docker compose up --build
```

- Backend API + frontend served on **:8989**
- Reports written to `./reports/`
- Config loaded from `./config/default.yaml` (mounted **read-write** so the
  in-app Settings screen can persist edits)
- Restart: `docker compose restart`

## Local development (no Docker)

Hot-reload for both ends, run in two terminals:

```bash
make dev-backend          # uv run uvicorn ... --reload --port 8989
make dev-frontend         # cd web-editor && npm install && npm run dev
```

- Frontend: <http://localhost:5173> (Vite hot-reload)
- API: <http://localhost:8989> (uvicorn `--reload`)
- Edit `src/` → backend reloads; edit `web-editor/src/` → browser reloads.

The Vite dev server proxies `/api`, `/run-scenario*`, `/session/*`, etc. to
`:8989` (see [web-editor/vite.config.ts](web-editor/vite.config.ts)).

## Configuration

`./config/default.yaml` is the single source of truth. Three ways to change it:

### 1. Settings screen (recommended, no restart)

Open the GUI → click the gear icon in the header. Edit Flight Blender URL,
auth, AMQP, OpenSky, simulator defaults, and data file paths. **Save & Apply**
writes back to the YAML (comments preserved) and hot-reloads the server.
**Reload** re-reads the file from disk.

> Note: *Save & Apply* is rejected while a scenario run is active — stop the
> run first.

### 2. Edit the YAML file directly

```bash
vim config/default.yaml
# Click Reload in the Settings screen — no restart needed.
# (Or: docker compose restart)
```

### 3. Environment variable / `.env` (build- or start-time)

```bash
FLIGHT_BLENDER_URL=http://my-blender:8000 make gui
```

> **Note:** `/session/reset` no longer accepts per-scenario config overrides.
> Use the Settings screen or PUT `/api/config` instead.

### Programmatic config update

```bash
curl -X PUT http://localhost:8989/api/config \
  -H "Content-Type: application/json" \
  -d '{"flight_blender": {"url": "https://blender.example.com",
                          "auth": {"type": "none"}}}'
```

## Reports

Generated reports land in `./reports/{timestamp}/`:

```
reports/2026-04-20_10-30-00/
├── report.json
├── report.html
├── report.log
└── <scenario_name>/
    ├── flight_declaration.json
    ├── telemetry.json
    └── air_traffic.json
```

View at <http://localhost:8989/reports/{timestamp}/report.html>.

## Troubleshooting

**Port already in use** — `lsof -i :8989` (Docker / backend) or `:5173`
(Vite dev).

**Permission denied on reports**
```bash
sudo chown -R 1000:1000 ./reports
```

**Settings screen "Save & Apply" fails with read-only error** — confirm both
`./config` and `./reports` mounts in `docker-compose.yml` are `:rw`.

**Reload button doesn't show external edits** — GET `/api/config` re-reads
from disk on every call. Rebuild if you're on an older image.

**Backend unreachable from host**
```bash
docker compose logs verification | tail -30
```

**Clean rebuild**
```bash
docker compose down
docker compose up --build
```

## Kubernetes

See [k8s-deployment.yaml](k8s-deployment.yaml) and
[docs/deployment-guide.md](docs/deployment-guide.md).

## More

- Architecture: [docs/gui-docker-architecture.md](docs/gui-docker-architecture.md)
- Default config: [config/default.yaml](config/default.yaml)
