import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import dependencies to ensure they are registered and steps are populated
import openutm_verification.core.execution.dependencies  # noqa: F401
from openutm_verification.core.execution.definitions import ScenarioDefinition
from openutm_verification.server.router import scenario_router
from openutm_verification.server.runner import SessionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    session_manager = SessionManager()
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
async def reset_session(runner: SessionManager = Depends(get_session_manager)):
    await runner.close_session()
    await runner.initialize_session()
    return {"status": "session_reset"}


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
