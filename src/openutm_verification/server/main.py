import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TypeVar

import uvicorn
from fastapi import Body, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel

# Import dependencies to ensure they are registered and steps are populated
import openutm_verification.core.execution.dependencies  # noqa: F401
from openutm_verification.core.execution.config_models import (
    AirTrafficSimulatorSettings,
    AppConfig,
    ConfigProxy,
    DataFiles,
    FlightBlenderConfig,
)
from openutm_verification.core.execution.definitions import ScenarioDefinition
from openutm_verification.core.reporting.reporting import create_report_data, generate_reports
from openutm_verification.core.reporting.reporting_models import (
    ScenarioResult,
    Status,
)
from openutm_verification.server.config_redaction import (
    redact_amqp,
    redact_auth,
    strip_redacted,
)
from openutm_verification.server.router import scenario_router
from openutm_verification.server.runner import SessionManager

T = TypeVar("T")

session_manager = SessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.runner = session_manager
    yield
    # Shutdown
    await session_manager.close_session()


app = FastAPI(lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenario_router)


def get_session_manager(request: Request) -> SessionManager:
    return request.app.state.runner


class SessionResetRequest(BaseModel):
    """Request model for session reset with optional configuration."""

    flight_blender: Optional[FlightBlenderConfig] = None
    data_files: Optional[DataFiles] = None
    air_traffic_simulator_settings: Optional[AirTrafficSimulatorSettings] = None


def start_server_mode(config_path: str | None = None, reload: bool = False):
    if config_path:
        os.environ["OPENUTM_CONFIG_PATH"] = str(config_path)

    # Allow environment variable to override reload setting
    reload = os.environ.get("UVICORN_RELOAD", str(reload)).lower() in ("true", "1", "yes")

    if reload:
        # Reload configuration to prevent high CPU from watching node_modules, .venv, etc.
        uvicorn.run(
            "openutm_verification.server.main:app",
            host="0.0.0.0",
            port=8989,
            reload=True,
            # Only watch the src directory for changes - dramatically reduces CPU usage
            reload_dirs=["src", "config"],
            # Explicitly exclude heavy directories
            reload_excludes=[
                "node_modules",
                ".venv",
                "__pycache__",
                ".git",
                "*.pyc",
                "reports",
                "htmlcov",
                "dist",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
                "web-editor",
            ],
        )
    else:
        uvicorn.run(
            "openutm_verification.server.main:app",
            host="0.0.0.0",
            port=8989,
        )


@app.get("/api/info")
async def api_info():
    return {"message": "OpenUTM Verification API is running"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/operations")
async def get_operations(runner: SessionManager = Depends(get_session_manager)):
    return runner.get_available_operations()


@app.get("/api/config")
async def get_config(runner: SessionManager = Depends(get_session_manager)):
    """Return the full server config the GUI manages.

    Re-reads the YAML from disk into a transient ``AppConfig`` so the GUI
    reflects out-of-band edits without touching the live session. The running
    session's ``runner.config`` is intentionally left alone here so that
    simply opening the Settings screen never resets an in-progress run.
    Falls back to the in-memory copy on parse errors so a transient bad file
    doesn't break the screen.

    Secrets (auth ``client_secret`` values, AMQP URL passwords) are redacted
    on response so the unauthenticated GUI/API never echoes credentials. The
    matching PUT endpoint ignores the redaction sentinel so round-tripping
    edits doesn't overwrite the stored secret with the placeholder.
    """
    import yaml as _yaml

    cfg = runner.config
    try:
        with open(runner.config_path, "r", encoding="utf-8") as f:
            raw = _yaml.safe_load(f)
        cfg = AppConfig.model_validate(raw)
    except Exception:  # noqa: BLE001
        logger.exception("Re-reading config during GET /api/config failed; serving in-memory copy")

    fb = cfg.flight_blender.model_dump()
    fb["auth"] = redact_auth(fb.get("auth", {}))
    opensky = cfg.opensky.model_dump()
    opensky["auth"] = redact_auth(opensky.get("auth", {}))

    return {
        "version": cfg.version,
        "run_id": cfg.run_id,
        "config_path": str(runner.config_path),
        "flight_blender": fb,
        "opensky": opensky,
        "amqp": redact_amqp(cfg.amqp.model_dump() if cfg.amqp else None),
        "data_files": cfg.data_files.model_dump(),
        "air_traffic_simulator_settings": (cfg.air_traffic_simulator_settings.model_dump() if cfg.air_traffic_simulator_settings else None),
    }


# Editable top-level keys via PUT /api/config. Other keys (suites, reporting)
# stay read-only because they have non-trivial side effects on path resolution
# and report layout that aren't worth exposing through the GUI right now.
_EDITABLE_CONFIG_KEYS = (
    "flight_blender",
    "opensky",
    "amqp",
    "air_traffic_simulator_settings",
    "data_files",
)


@app.put("/api/config")
async def put_config(
    payload: dict = Body(...),
    runner: SessionManager = Depends(get_session_manager),
):
    """Persist edited config sections back to the loaded YAML file and reload.

    Only the keys in ``_EDITABLE_CONFIG_KEYS`` are honored. Comments and
    formatting in the file are preserved via ruamel.yaml round-trip mode.
    Refuses to save while a scenario is running (the reload would tear down
    in-flight clients). Validates the candidate config before writing, and
    writes atomically (temp file + rename) so a failed save can never leave
    a half-written YAML on disk.
    """
    from pydantic import ValidationError
    from ruamel.yaml import YAML

    if runner.current_run_task is not None and not runner.current_run_task.done():
        return {
            "status": "error",
            "message": "Cannot save config while a scenario is running. Stop the run first.",
        }

    config_path = runner.config_path
    if not config_path.exists():
        return {"status": "error", "message": f"Config file not found: {config_path}"}

    yaml_rt = YAML()
    yaml_rt.preserve_quotes = True
    yaml_rt.indent(mapping=2, sequence=4, offset=2)

    with open(config_path, "r", encoding="utf-8") as f:
        doc = yaml_rt.load(f)

    applied: list[str] = []
    for key in _EDITABLE_CONFIG_KEYS:
        # Apply the key whenever it appears in the payload, including when
        # its value is null, so the GUI can clear optional sections (e.g.
        # set ``amqp: null`` to remove AMQP config).
        if key in payload:
            doc[key] = strip_redacted(key, payload[key], doc.get(key))
            applied.append(key)

    # Validate the would-be config before touching disk so we never persist
    # a broken YAML that would block future reloads/restarts.
    try:
        AppConfig.model_validate(dict(doc))
    except ValidationError as exc:
        logger.warning(f"Rejected config save to {config_path}: validation failed")
        return {"status": "error", "message": f"Invalid config: {exc}"}

    tmp_path = config_path.with_suffix(config_path.suffix + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            yaml_rt.dump(doc, f)
        os.replace(tmp_path, config_path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    logger.info(f"Wrote {applied} to {config_path}; reloading config")
    try:
        await runner.reload_config()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Reload after config save failed")
        return {"status": "saved_but_reload_failed", "applied": applied, "error": str(exc)}

    return {"status": "saved", "applied": applied, "config_path": str(config_path)}


@app.post("/session/reset")
async def reset_session(
    config: SessionResetRequest = Body(default_factory=SessionResetRequest, embed=True),
    runner: SessionManager = Depends(get_session_manager),
):
    """Reset session and optionally apply new configuration.

    The configuration from the frontend allows users to:
    - Override Flight Blender connection details
    - Specify data file paths
    - Configure air traffic simulator settings
    """

    logger.debug(f"Session reset request received: {config.model_dump()}")

    await runner.close_session()
    runner.current_output_dir = None
    runner.current_timestamp_str = None
    runner.current_start_time = None

    # If configuration is provided from the frontend, apply it
    if config.flight_blender:
        runner.config.flight_blender = config.flight_blender
        logger.info(f"Applied Flight Blender config: {config.flight_blender.url}")
    if config.data_files:
        current_data_files = runner.config.data_files
        updates = {k: v for k, v in config.data_files.model_dump().items() if v is not None}
        runner.config.data_files = current_data_files.model_copy(update=updates)
        logger.info("Applied data files config (merged overrides)")
    if config.air_traffic_simulator_settings:
        runner.config.air_traffic_simulator_settings = config.air_traffic_simulator_settings
        logger.info("Applied air traffic simulator settings")

    # Refresh global config proxy so dependency settings use updated values
    ConfigProxy.override(runner.config)

    await runner.initialize_session()
    return {"status": "session_reset"}


class GenerateReportRequest(BaseModel):
    scenario_name: str = "Interactive Session"


@app.post("/session/generate-report")
async def generate_report_endpoint(request: GenerateReportRequest, runner: SessionManager = Depends(get_session_manager)):
    if not runner.session_context or not runner.session_context.state:
        return {"status": "error", "message": "No active session"}

    # Construct ScenarioResult
    state = runner.session_context.state
    # Filter out steps without ID or name (though name is required)
    steps = state.steps

    # Determine status
    failed = any(s.status == Status.FAIL for s in steps)
    status = Status.FAIL if failed else Status.PASS

    scenario_result = ScenarioResult(
        name=request.scenario_name,
        status=status,
        duration=0.0,  # TODO: Track duration
        steps=steps,
        flight_declaration_data=state.flight_declaration_data,
        flight_declaration_via_operational_intent_data=state.flight_declaration_via_operational_intent_data,
        telemetry_data=state.telemetry_data,
        air_traffic_data=state.air_traffic_data,
    )

    # Construct ReportData
    end_timestamp = datetime.now(timezone.utc)
    # Use stored start time from scenario run, or fall back to end time
    start_timestamp = runner.current_start_time or end_timestamp
    # Sanitize scenario name for filename: keep only alphanumerics and underscores
    safe_name = "".join(c if c.isalnum() else "_" for c in request.scenario_name)
    run_id = f"{safe_name}_{end_timestamp.strftime('%Y%m%d_%H%M%S')}"

    # Get config
    config = runner.config

    report_data = create_report_data(
        config=config,
        config_path=str(runner.config_path),
        results=[scenario_result],
        start_time=start_timestamp,
        end_time=end_timestamp,
        run_id=run_id,
        docs_dir=None,
    )

    try:
        # Use the output directory from the scenario run if available
        # This ensures reports are saved in the same directory as the log file
        if runner.current_timestamp_str:
            config.reporting.timestamp_subdir = runner.current_timestamp_str
        else:
            # Fallback: create a new timestamp directory
            config.reporting.timestamp_subdir = ""
        generate_reports(
            report_data,
            config.reporting,
        )

        # Get the actual report directory for the response
        report_id = runner.current_timestamp_str or run_id
        return {"status": "success", "report_id": report_id}
    except Exception as e:
        print(f"Error generating report: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/run-scenario")
async def run_scenario(scenario: ScenarioDefinition, runner: SessionManager = Depends(get_session_manager)):
    return await runner.run_scenario(scenario)


@app.post("/run-scenario-async")
async def run_scenario_async(scenario: ScenarioDefinition, runner: SessionManager = Depends(get_session_manager)):
    run_id = await runner.start_scenario_task(scenario)
    return {"run_id": run_id}


@app.post("/stop-scenario")
async def stop_scenario(runner: SessionManager = Depends(get_session_manager)):
    """Stop the currently running scenario."""
    stopped = await runner.stop_scenario()
    return {"stopped": stopped}


@app.get("/run-scenario-events")
async def run_scenario_events(runner: SessionManager = Depends(get_session_manager)):
    async def event_stream():
        # Track consecutive idle iterations for adaptive sleep
        idle_iterations = 0

        while True:
            status_payload = runner.get_run_status()

            # Safely check for results - handle None session_context or state
            had_results = False
            if runner.session_context and runner.session_context.state:
                while not runner.session_context.state.added_results.empty():
                    result = runner.session_context.state.added_results.get_nowait()
                    yield f"data: {result.model_dump_json()}\n\n"
                    had_results = True
                    idle_iterations = 0

            if status_payload.get("status") != "running" and not runner.has_pending_tasks():
                done_payload = {
                    "status": status_payload.get("status"),
                    "error": status_payload.get("error"),
                }
                yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
                break

            # Adaptive sleep: longer when idle, shorter when active
            if had_results:
                await asyncio.sleep(0.1)  # Fast polling when receiving results
            else:
                idle_iterations += 1
                # Gradually increase sleep time when idle (max 1 second)
                sleep_time = min(0.3 + (idle_iterations * 0.1), 1.0)
                await asyncio.sleep(sleep_time)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# Mount static files for web-editor
# Calculate path relative to this file
# src/openutm_verification/server/main.py -> ../../../web-editor/dist
web_editor_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../web-editor"))

# Allow override via environment variable (e.g. for Docker production builds)
web_editor_dir = os.environ.get("WEB_EDITOR_PATH", web_editor_dir)

# Use dist directory - check_dir=False avoids repeated filesystem checks
static_dir = os.path.join(web_editor_dir, "dist")

# Mount reports directory BEFORE the catch-all "/" route
# This ensures /reports requests are handled correctly
try:
    output_dir = Path(session_manager.config.reporting.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # check_dir=False prevents repeated directory existence checks
    app.mount("/reports", StaticFiles(directory=str(output_dir), check_dir=False), name="reports")
    logger.info(f"Mounted reports directory at /reports -> {output_dir}")
except Exception as e:
    logger.warning(f"Could not mount reports directory: {e}")

if os.path.exists(static_dir):
    # check_dir=False - we already verified the directory exists above
    app.mount("/", StaticFiles(directory=static_dir, html=True, check_dir=False), name="static")
else:

    @app.get("/")
    async def root():
        return {
            "message": "OpenUTM Verification API is running.",
            "hint": "To use the web editor, run 'npm run build' in the web-editor directory. Automatic build failed or npm was not found.",
        }


if __name__ == "__main__":
    start_server_mode(reload=True)
