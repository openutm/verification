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

from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.execution.config_models import config
from openutm_verification.core.execution.scenario_runner import ScenarioContext
from openutm_verification.core.reporting.reporting_models import (
    ScenarioResult,
    Status,
    StepResult,
)
from openutm_verification.scenarios.common import (
    generate_flight_declaration,
    generate_telemetry,
)

SCENARIO_REGISTRY = {}
T = TypeVar("T")


@dataclass
class SetupData:
    operation_id: str
    flight_declaration: Any
    telemetry_states: List[Any]
    upload_result: StepResult


def _extract_arg(args: tuple, kwargs: dict, type: Type[T]) -> T | None:
    """Helper to extract FlightBlenderClient from args or kwargs."""
    for arg in list(kwargs.values()) + list(args):
        if isinstance(arg, type):
            return arg
    return None


def _perform_setup(scenario_id: str, fb_client: FlightBlenderClient) -> SetupData:
    """Generates data and uploads flight declaration."""
    scenario_config = config.scenarios.get(scenario_id)
    if scenario_config is None:
        scenario_config = config.data_files

    telemetry_path = scenario_config.telemetry or config.data_files.telemetry
    flight_declaration_path = (
        scenario_config.flight_declaration or config.data_files.flight_declaration
    )

    flight_declaration = generate_flight_declaration(flight_declaration_path)
    telemetry_states = generate_telemetry(telemetry_path)

    fb_client.telemetry_states = telemetry_states

    upload_result = cast(
        StepResult, fb_client.upload_flight_declaration(flight_declaration)
    )

    if upload_result.status == Status.FAIL:
        # We still return data, but operation_id might be missing/invalid if failed
        # The caller should check upload_result.status
        return SetupData(
            operation_id="",
            flight_declaration=flight_declaration,
            telemetry_states=telemetry_states,
            upload_result=upload_result,
        )

    return SetupData(
        operation_id=upload_result.details["id"],
        flight_declaration=flight_declaration,
        telemetry_states=telemetry_states,
        upload_result=upload_result,
    )


def _run_scenario_with_setup(
    scenario_id: str, fb_client: FlightBlenderClient, func, args, kwargs
) -> ScenarioResult:
    """Runs a scenario with auto-setup and teardown."""
    logger.info(
        f"Scenario '{scenario_id}' requires flight declaration setup. Applying auto-setup."
    )

    try:
        setup_data = _perform_setup(scenario_id, fb_client)
    except Exception as setup_error:
        logger.error(f"Setup failed for scenario '{scenario_id}': {setup_error}")
        return ScenarioResult(
            name=scenario_id,
            status=Status.FAIL,
            duration_seconds=0,
            steps=[],
            error_message=f"Setup failed: {setup_error}",
        )

    if setup_data.upload_result.status == Status.FAIL:
        return ScenarioResult(
            name=scenario_id,
            status=Status.FAIL,
            duration_seconds=setup_data.upload_result.duration,
            steps=[setup_data.upload_result],
            error_message="Failed to upload flight declaration during setup.",
        )

    steps: List[StepResult] = [setup_data.upload_result]
    ctx = ScenarioContext()
    try:
        with ctx:
            func(*args, **kwargs)
    except Exception as run_error:
        logger.error(f"Execution failed for scenario '{scenario_id}': {run_error}")
        steps.append(
            StepResult(
                name="Scenario Execution",
                status=Status.FAIL,
                duration=0,
                error_message=str(run_error),
            )
        )
    finally:
        steps.extend(ctx.steps)

    teardown_result = cast(
        StepResult, fb_client.delete_flight_declaration(setup_data.operation_id)
    )
    steps.append(teardown_result)

    final_status = (
        Status.PASS if all(s.status == Status.PASS for s in steps) else Status.FAIL
    )
    total_duration = sum(s.duration for s in steps)

    return ScenarioResult(
        name=scenario_id,
        status=final_status,
        duration_seconds=total_duration,
        steps=steps,
        flight_declaration_data=setup_data.flight_declaration,
        telemetry_data=setup_data.telemetry_states,
    )


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


def register_scenario(scenario_id: str, setup_flight_declaration: bool = False):
    """
    A decorator to register a test scenario function.

    Args:
        scenario_id (str): The unique identifier for the scenario.
                           This ID is used in the configuration file.
        setup_flight_declaration (bool): If True, automatically generates and uploads a flight declaration
                                         and telemetry data before running the scenario, and cleans up afterwards.
    """

    def decorator(func):
        if scenario_id in SCENARIO_REGISTRY:
            raise ValueError(f"Scenario with ID '{scenario_id}' is already registered.")

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Identify fb_client
            fb_client = _extract_arg(args, kwargs, FlightBlenderClient)

            if setup_flight_declaration and fb_client:
                return _run_scenario_with_setup(
                    scenario_id, fb_client, func, args, kwargs
                )

            return _run_scenario_simple(scenario_id, func, args, kwargs)

        SCENARIO_REGISTRY[scenario_id] = wrapper
        return wrapper

    return decorator
