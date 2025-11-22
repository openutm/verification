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

from dataclasses import dataclass
from functools import wraps
from typing import Any, List, Type, TypeVar, cast

from loguru import logger

from openutm_verification.core.execution.config_models import config
from openutm_verification.core.execution.scenario_runner import ScenarioContext
from openutm_verification.core.reporting.reporting_models import (
    ScenarioResult,
    Status,
    StepResult,
)

SCENARIO_REGISTRY = {}
T = TypeVar("T")








def _run_scenario_simple(scenario_id: str, func, args, kwargs) -> ScenarioResult:
    """Runs a scenario without auto-setup."""
    try:
        with ScenarioContext() as ctx:
            result = func(*args, **kwargs)

            if isinstance(result, ScenarioResult):
                return result

            steps = ctx.steps

        final_status = (
            Status.PASS if all(s.status == Status.PASS for s in steps) else Status.FAIL
        )
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


def register_scenario(scenario_id: str):
    """
    A decorator to register a test scenario function.

    Args:
        scenario_id (str): The unique identifier for the scenario.
                           This ID is used in the configuration file.
    """

    def decorator(func):
        if scenario_id in SCENARIO_REGISTRY:
            raise ValueError(f"Scenario with ID '{scenario_id}' is already registered.")

        @wraps(func)
        def wrapper(*args, **kwargs):
            return _run_scenario_simple(scenario_id, func, args, kwargs)

        SCENARIO_REGISTRY[scenario_id] = wrapper
        return wrapper

    return decorator
