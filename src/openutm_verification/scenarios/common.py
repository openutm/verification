from functools import partial
from pathlib import Path
from typing import Any, List

from loguru import logger

from openutm_verification.config_models import ScenarioResult, Status, StepResult
from openutm_verification.flight_blender_client import FlightBlenderClient


def run_scenario_template(
    client: FlightBlenderClient,
    scenario_name: str,
    flight_declaration_filename: str,
    telemetry_filename: str,
    steps: list[partial[Any]],
) -> ScenarioResult:
    """
    A template for running a standard verification scenario.

    This function handles the common setup and teardown for a scenario, including:
    1. Uploading a flight declaration.
    2. Executing a list of scenario-specific steps.
    3. Calculating the final status and duration.

    Args:
        client: The FlightBlenderClient instance.
        scenario_name: The name of the scenario for reporting.
        flight_declaration_filename: The filename of the flight declaration asset.
        steps: A list of callable functions representing the unique
               steps of the scenario. Each callable should accept the
               operation ID.
        telemetry_filename: Optional name of the telemetry file.
    """
    flight_declaration_path = get_flight_declaration_path(flight_declaration_filename)
    telemetry_path = get_telemetry_path(telemetry_filename)

    # First step is always to upload the flight declaration
    upload_result: StepResult = client.upload_flight_declaration(filename=flight_declaration_path)

    if upload_result.status == Status.FAIL or upload_result.details is None:
        error_message: str | None = (
            upload_result.error_message if upload_result.status == Status.FAIL else "Flight declaration step passed but returned no details."
        )
        return ScenarioResult(
            name=scenario_name,
            status=Status.FAIL,
            duration_seconds=upload_result.duration,
            steps=[upload_result],
            error_message=error_message,
        )

    operation_id = upload_result.details["id"]

    # Execute all subsequent steps
    all_steps: List[StepResult] = [upload_result]
    for step_func in steps:
        # Pass telemetry_path to steps that need it
        kwargs = {}
        # Check if the step is the telemetry submission step
        if "submit_telemetry" in step_func.func.__name__:
            kwargs["filename"] = telemetry_path

        step_result: StepResult = step_func(operation_id, **kwargs)
        all_steps.append(step_result)
        if step_result.status == Status.FAIL:
            break  # Stop scenario on first failure

    # Teardown: Delete created flight declaration
    teardown_result: StepResult = client.delete_flight_declaration(operation_id)
    all_steps.append(teardown_result)

    final_status = Status.PASS if all(step.status == Status.PASS for step in all_steps) else Status.FAIL
    total_duration = sum(step.duration for step in all_steps)

    return ScenarioResult(
        name=scenario_name,
        status=final_status,
        duration_seconds=total_duration,
        steps=all_steps,
    )


def get_telemetry_path(telemetry_filename: str) -> str:
    """Helper to get the full path to a telemetry file."""
    parent_dir = Path(__file__).parent.resolve()
    return str(parent_dir / f"../assets/rid_samples/{telemetry_filename}")


def get_flight_declaration_path(flight_declaration_filename: str) -> str:
    """Helper to get the full path to a flight declaration file."""
    parent_dir = Path(__file__).parent.resolve()
    return str(parent_dir / f"../assets/flight_declarations_samples/{flight_declaration_filename}")
