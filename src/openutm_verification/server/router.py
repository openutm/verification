from pathlib import Path
from typing import Any, Type, TypeVar

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, RedirectResponse

from openutm_verification.core.execution.definitions import ScenarioDefinition, StepDefinition
from openutm_verification.core.execution.scenario_loader import load_yaml_scenario_definition
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
    """List all available scenarios, including those in sub-folders."""
    path = get_scenarios_directory()
    if not path.exists():
        return []
    return [str(f.relative_to(path).with_suffix("")) for f in sorted(path.rglob("*.yaml"))]


@scenario_router.get("/api/suites")
async def list_suites(runner: Any = Depends(get_runner)):
    """Return suite-to-scenario mapping, resolving bare names to subfolder-relative paths."""
    scenarios_path = get_scenarios_directory()
    # Build a mapping from stem to all matching scenario IDs to detect ambiguities.
    stem_to_ids: dict[str, list[str]] = {}
    for f in scenarios_path.rglob("*.yaml"):
        stem = f.stem
        scenario_id = str(f.relative_to(scenarios_path).with_suffix(""))
        stem_to_ids.setdefault(stem, []).append(scenario_id)

    def resolve_scenario_name(name: str) -> str:
        """Resolve a bare scenario name to its ID if unambiguous.

        If there are no scenarios with the given stem, or if multiple scenarios
        share the same stem, return the name unchanged so callers can use a
        fully-qualified ID instead.
        """
        ids = stem_to_ids.get(name)
        if not ids:
            # No matching stem; leave as-is.
            return name
        if len(ids) == 1:
            # Unique stem; safe to auto-resolve.
            return ids[0]
        # Ambiguous stem; do not auto-resolve to avoid silently picking one.
        return name

    config = runner.config
    result: dict[str, list[str]] = {}
    for suite_name, suite_config in config.suites.items():
        if suite_config.scenarios:
            result[suite_name] = [resolve_scenario_name(s.name) for s in suite_config.scenarios]
        else:
            result[suite_name] = []
    return result


@scenario_router.get("/api/scenarios/{scenario:path}/docs")
async def get_scenario_docs(scenario: str):
    """Get the documentation for a specific scenario."""
    docs_dir = get_docs_directory()
    file_path = (docs_dir / scenario).with_suffix(".md").resolve()
    if not file_path.is_relative_to(docs_dir.resolve()):
        raise HTTPException(status_code=404, detail="Documentation not found")
    if not file_path.exists():
        # Fallback: search by stem for flat doc files not yet reorganised into subfolders
        stem = Path(scenario).stem
        matches = list(docs_dir.rglob(f"{stem}.md"))
        if len(matches) == 1:
            file_path = matches[0]
        else:
            raise HTTPException(status_code=404, detail="Documentation not found")

    with open(file_path, "r") as f:
        return PlainTextResponse(f.read())


@scenario_router.get("/api/scenarios/{scenario:path}")
async def get_scenario(scenario: str):
    """Get the content of a specific scenario."""
    try:
        scenario_def = load_yaml_scenario_definition(scenario)
        return scenario_def.model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Scenario not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invalid YAML: {e}")


@scenario_router.post("/api/scenarios/{name:path}")
async def save_scenario(name: str, scenario: ScenarioDefinition):
    """Save a scenario to a YAML file."""
    path = get_scenarios_directory()
    file_path = (path / name).with_suffix(".yaml")

    # Ensure directory exists (including any sub-folder)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Convert Pydantic model to dict, excluding None values to keep YAML clean
        data = scenario.model_dump(exclude_none=True, exclude_defaults=True)

        with open(file_path, "w") as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False)

        return {"message": f"Scenario saved to {file_path.name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save scenario: {e}")


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
