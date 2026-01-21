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

import inspect
from functools import wraps
from typing import Any, Callable, Coroutine, ParamSpec, TypeVar

from loguru import logger

from openutm_verification.core.execution.scenario_runner import (
    ScenarioContext,
    ScenarioRegistry,
    _scenario_state,
)
from openutm_verification.core.reporting.reporting_models import (
    ScenarioResult,
    Status,
)
from openutm_verification.utils.paths import get_docs_directory

SCENARIO_REGISTRY: dict[str, ScenarioRegistry] = {}
T = TypeVar("T")
P = ParamSpec("P")


async def _run_scenario_simple_async(scenario_id: str, func: Callable, args, kwargs) -> ScenarioResult:
    """Runs a scenario without auto-setup (async)."""
    try:
        # Reuse existing state if available (e.g. from SessionManager)
        current_state = _scenario_state.get()
        ctx_manager = ScenarioContext(state=current_state) if current_state else ScenarioContext()

        with ctx_manager as ctx:
            result = await func(*args, **kwargs)

            if isinstance(result, ScenarioResult):
                return result

            steps = ctx.steps
            flight_declaration_data = ctx.flight_declaration_data
            flight_declaration_via_operational_intent_data = ctx.flight_declaration_via_operational_intent_data
            telemetry_data = ctx.telemetry_data
            air_traffic_data = ctx.air_traffic_data

        final_status = Status.PASS if all(s.status == Status.PASS for s in steps) else Status.FAIL
        total_duration = sum(s.duration for s in steps)
        return ScenarioResult(
            name=scenario_id,
            status=final_status,
            duration=total_duration,
            steps=steps,
            flight_declaration_data=flight_declaration_data,
            flight_declaration_via_operational_intent_data=flight_declaration_via_operational_intent_data,
            telemetry_data=telemetry_data,
            air_traffic_data=air_traffic_data,
        )

    except Exception as e:
        logger.error(f"Scenario '{scenario_id}' failed: {e}")
        raise e


def register_scenario(
    scenario_id: str,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, Any]]],
    Callable[P, Coroutine[Any, Any, ScenarioResult]],
]:
    """
    A decorator to register a test scenario function.

    Args:
        scenario_id (str): The unique identifier for the scenario.
                           This ID is used in the configuration file.
    """

    def decorator(
        func: Callable[P, Coroutine[Any, Any, Any]],
    ) -> Callable[P, Coroutine[Any, Any, ScenarioResult]]:
        if scenario_id in SCENARIO_REGISTRY:
            raise ValueError(f"Scenario with ID '{scenario_id}' is already registered.")

        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> ScenarioResult:
                return await _run_scenario_simple_async(scenario_id, func, args, kwargs)

            wrapper = async_wrapper
        else:
            raise ValueError(f"Scenario function {func.__name__} must be async")

        docs_dir = get_docs_directory()
        docs_path = docs_dir / f"{scenario_id}.md" if docs_dir else None
        SCENARIO_REGISTRY[scenario_id] = {"func": wrapper, "docs": docs_path}
        return wrapper  # type: ignore

    return decorator
