from pathlib import Path
from typing import Any, Type, TypeVar

import yaml
from fastapi import APIRouter, Depends, HTTPException, Request

from openutm_verification.core.execution.definitions import ScenarioDefinition, StepDefinition

T = TypeVar("T")

scenario_router = APIRouter()

# Define the scenarios directory relative to this file
# src/openutm_verification/server/router.py -> .../scenarios
SCENARIOS_DIR = Path(__file__).parents[3] / "scenarios"


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
    if not SCENARIOS_DIR.exists():
        return []
    return [f.stem for f in SCENARIOS_DIR.glob("*.yaml")]


@scenario_router.get("/api/scenarios/{scenario}")
async def get_scenario(scenario: str):
    """Get the content of a specific scenario."""
    file_path = (SCENARIOS_DIR / scenario).with_suffix(".yaml")
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
    file_path = (SCENARIOS_DIR / name).with_suffix(".yaml")

    # Ensure directory exists
    SCENARIOS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # Convert Pydantic model to dict, excluding None values to keep YAML clean
        data = scenario.model_dump(exclude_none=True, exclude_defaults=True)

        with open(file_path, "w") as f:
            yaml.dump(data, f, sort_keys=False, default_flow_style=False)

        return {"message": f"Scenario saved to {file_path.name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save scenario: {e}")
