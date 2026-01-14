from pathlib import Path
from typing import Any, Type, TypeVar

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

from openutm_verification.core.execution.definitions import ScenarioDefinition, StepDefinition
from openutm_verification.utils.paths import get_docs_directory, get_scenarios_directory

T = TypeVar("T")

scenario_router = APIRouter()


def get_runner(request: Request) -> Any:
    return request.app.state.runner


def get_dependency(dep_type: Type[T]):
    async def dependency(runner: Any = Depends(get_runner)) -> T:
        # Ensure session is initialized
        if not runner.session_resolver:
            await runner.initialize_session()
        return await runner.session_resolver.resolve(dep_type)

    return dependency


@scenario_router.post("/api/step")
async def execute_step(step: StepDefinition, runner: Any = Depends(get_runner)):
    return await runner.execute_single_step(step)


@scenario_router.get("/api/scenarios")
async def list_scenarios():
    """List all available scenarios."""
    path = get_scenarios_directory()
    if not path.exists():
        return []
    return [f.stem for f in path.glob("*.yaml")]


@scenario_router.get("/api/scenarios/{scenario}")
async def get_scenario(scenario: str):
    """Get the content of a specific scenario."""
    path = get_scenarios_directory()
    file_path = (path / scenario).with_suffix(".yaml")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Scenario not found")

    with open(file_path, "r") as f:
        try:
            content = yaml.safe_load(f)
            return content
        except yaml.YAMLError as e:
            raise HTTPException(status_code=500, detail=f"Invalid YAML: {e}")


@scenario_router.post("/api/scenarios/{name}")
async def save_scenario(name: str, scenario: ScenarioDefinition):
    """Save a scenario to a YAML file."""
    path = get_scenarios_directory()
    file_path = (path / name).with_suffix(".yaml")

    # Ensure directory exists
    path.mkdir(parents=True, exist_ok=True)

    try:
        # Convert Pydantic model to dict, excluding None values to keep YAML clean
        data = scenario.model_dump(exclude_none=True, exclude_defaults=True)

        with open(file_path, "w") as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False)

        return {"message": f"Scenario saved to {file_path.name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save scenario: {e}")


@scenario_router.get("/api/scenarios/{scenario}/docs")
async def get_scenario_docs(scenario: str):
    """Get the documentation for a specific scenario."""
    file_path = (get_docs_directory() / scenario).with_suffix(".md")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Documentation not found")

    with open(file_path, "r") as f:
        content = f.read()
        return PlainTextResponse(content)


@scenario_router.get("/api/reports/latest")
async def get_latest_report(request: Request, scenario: str | None = None):
    """Redirect to the latest generated report. Optionally filter by scenario name."""
    runner = request.app.state.runner
    output_dir = Path(runner.config.reporting.output_dir)

    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Reports directory not found")

    # Get all subdirectories that might contain reports
    runs = [d for d in output_dir.iterdir() if d.is_dir()]
    if not runs:
        raise HTTPException(status_code=404, detail="No reports found")

    if scenario:
        runs = [d for d in runs if (d / scenario).exists()]
        if not runs:
            raise HTTPException(status_code=404, detail=f"No reports found for scenario '{scenario}'")

    # Sort by directory name (timestamp) to find the latest
    latest_run = sorted(runs, key=lambda d: d.name)[-1]

    report_file = latest_run / "report.html"
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Report file not found in latest run")

    # Construct URL relative to the mounted /reports path
    relative_path = report_file.relative_to(output_dir)
    url = f"/reports/{relative_path}"

    return RedirectResponse(url=url)
