import os
import shutil
import subprocess
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

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
static_dir = os.path.join(web_editor_dir, "dist")


def build_frontend():
    """Attempt to build the web-editor frontend using npm."""
    if not os.path.exists(web_editor_dir):
        logger.warning(f"Web editor directory not found at {web_editor_dir}")
        return

    npm_cmd = shutil.which("npm")
    if not npm_cmd:
        logger.warning("npm not found. Skipping web editor build.")
        return

    try:
        logger.info("Building web editor frontend... This may take a while.")
        # Run npm install
        logger.info("Running 'npm install'...")
        subprocess.run([npm_cmd, "install"], cwd=web_editor_dir, check=True)

        # Run npm run build
        logger.info("Running 'npm run build'...")
        subprocess.run([npm_cmd, "run", "build"], cwd=web_editor_dir, check=True)

        logger.info("Web editor built successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to build web editor: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during web editor build: {e}")


if not os.path.exists(static_dir):
    build_frontend()

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
    import uvicorn

    uvicorn.run(
        "openutm_verification.server.main:app",
        host="0.0.0.0",
        port=8989,
        reload=True,
        reload_includes=["*.py"],
    )
