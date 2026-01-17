import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TypeVar

import uvicorn
from fastapi import Body, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel

# Import dependencies to ensure they are registered and steps are populated
import openutm_verification.core.execution.dependencies  # noqa: F401
from openutm_verification.core.execution.config_models import (
    AirTrafficSimulatorSettings,
    DataFiles,
    FlightBlenderConfig,
)
from openutm_verification.core.execution.definitions import ScenarioDefinition
from openutm_verification.core.reporting.reporting import create_report_data, generate_reports
from openutm_verification.core.reporting.reporting_models import (
    ScenarioResult,
    Status,
)
from openutm_verification.server.router import scenario_router
from openutm_verification.server.runner import SessionManager

T = TypeVar("T")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    session_manager = SessionManager()
    app.state.runner = session_manager

    # Mount reports directory after session manager is ready to avoid import-time side effects
    try:
        output_dir = Path(session_manager.config.reporting.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/reports", StaticFiles(directory=str(output_dir)), name="reports")
    except Exception as e:
        logger.warning(f"Could not mount reports directory: {e}")

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
    uvicorn.run(
        "openutm_verification.server.main:app",
        host="0.0.0.0",
        port=8989,
        reload=reload,
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

    # If configuration is provided from the frontend, apply it
    if config.flight_blender:
        runner.config.flight_blender = config.flight_blender
        logger.info(f"Applied Flight Blender config: {config.flight_blender.url}")
    if config.data_files:
        runner.config.data_files = config.data_files
        logger.info("Applied data files config")
    if config.air_traffic_simulator_settings:
        runner.config.air_traffic_simulator_settings = config.air_traffic_simulator_settings
        logger.info("Applied air traffic simulator settings")

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
    run_timestamp = datetime.now(timezone.utc)
    # Sanitize scenario name for filename: keep only alphanumerics and underscores
    safe_name = "".join(c if c.isalnum() else "_" for c in request.scenario_name)
    run_id = f"{safe_name}_{run_timestamp.strftime('%Y%m%d_%H%M%S')}"

    # Get config
    config = runner.config

    report_data = create_report_data(
        config=config,
        config_path=str(runner.config_path),
        results=[scenario_result],
        start_time=run_timestamp,
        end_time=run_timestamp,
        run_id=run_id,
        docs_dir=None,
    )

    try:
        # Save report to a specifically named run subdirectory
        generate_reports(
            report_data,
            config.reporting,
        )
        return {"status": "success", "report_id": run_id}
    except Exception as e:
        print(f"Error generating report: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/run-scenario")
async def run_scenario(scenario: ScenarioDefinition, runner: SessionManager = Depends(get_session_manager)):
    return await runner.run_scenario(scenario)


# Mount static files for web-editor
# Calculate path relative to this file
# src/openutm_verification/server/main.py -> ../../../web-editor/dist
web_editor_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../web-editor"))

# Allow override via environment variable (e.g. for Docker production builds)
web_editor_dir = os.environ.get("WEB_EDITOR_PATH", web_editor_dir)

static_dir = os.path.join(web_editor_dir, "dist")


if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:

    @app.get("/")
    async def root():
        return {
            "message": "OpenUTM Verification API is running.",
            "hint": "To use the web editor, run 'npm run build' in the web-editor directory. Automatic build failed or npm was not found.",
        }


if __name__ == "__main__":
    start_server_mode(reload=True)
