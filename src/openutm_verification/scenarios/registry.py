"""
A module for registering test scenarios.

This module provides a decorator-based registration system for test scenarios.
To register a new scenario, apply the `@register_scenario` decorator to your
scenario function.

Example:
    from openutm_verification.scenarios.registry import register_scenario

    @register_scenario("my_scenario_id")
    def run_my_scenario(client, scenario_id):
        # ...
"""

from functools import wraps
from pathlib import Path
from typing import Any, Callable, ParamSpec, TypeVar

from loguru import logger

from openutm_verification.core.execution.scenario_runner import ScenarioContext, ScenarioRegistry
from openutm_verification.core.reporting.reporting_models import (
    ScenarioResult,
    Status,
)

SCENARIO_REGISTRY: dict[str, ScenarioRegistry] = {}
T = TypeVar("T")
P = ParamSpec("P")


def _run_scenario_simple(scenario_id: str, func: Callable, args, kwargs) -> ScenarioResult:
    """Runs a scenario without auto-setup."""
    try:
        with ScenarioContext() as ctx:
            result = func(*args, **kwargs)

            if isinstance(result, ScenarioResult):
                return result

            steps = ctx.steps

        final_status = Status.PASS if all(s.status == Status.PASS for s in steps) else Status.FAIL
        total_duration = sum(s.duration for s in steps)
        return ScenarioResult(
            name=scenario_id,
            status=final_status,
            duration_seconds=total_duration,
            steps=steps,
        )

    except Exception as e:
        logger.error(f"Scenario '{scenario_id}' failed: {e}")
        raise e


def register_scenario(
    scenario_id: str,
) -> Callable[[Callable[P, Any]], Callable[P, ScenarioResult]]:
    """
    A decorator to register a test scenario function.

    Args:
        scenario_id (str): The unique identifier for the scenario.
                           This ID is used in the configuration file.
    """

    def decorator(func: Callable[P, Any]) -> Callable[P, ScenarioResult]:
        if scenario_id in SCENARIO_REGISTRY:
            raise ValueError(f"Scenario with ID '{scenario_id}' is already registered.")

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> ScenarioResult:
            return _run_scenario_simple(scenario_id, func, args, kwargs)

        # Determine docs path
        # 1. Try installed package location: openutm_verification/docs/scenarios/{scenario_id}.md
        package_root = Path(__file__).parent.parent
        docs_dir = package_root / "docs" / "scenarios"

        if not docs_dir.exists():
            # 2. Try development location: project_root/docs/scenarios/{scenario_id}.md
            # registry.py is in src/openutm_verification/scenarios/
            docs_dir = Path(__file__).parents[3] / "docs" / "scenarios"

        docs_path = docs_dir / f"{scenario_id}.md"

        # Fallback to side-by-side if docs dir file doesn't exist
        if not docs_path.exists():
            func_file = Path(func.__code__.co_filename)
            side_by_side_path = func_file.with_suffix(".md")
            if side_by_side_path.exists():
                docs_path = side_by_side_path

        SCENARIO_REGISTRY[scenario_id] = {"func": wrapper, "docs": docs_path}
        return wrapper

    return decorator
