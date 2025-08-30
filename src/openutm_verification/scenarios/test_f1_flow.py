from functools import partial

from openutm_verification.config_models import ScenarioResult
from openutm_verification.flight_blender_client import FlightBlenderClient
from openutm_verification.models import OperationState
from openutm_verification.scenarios.common import run_scenario_template
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("F1_happy_path")
def test_f1_happy_path(client: FlightBlenderClient, scenario_name: str) -> ScenarioResult:
    """Runs the F1 happy path scenario.

    This scenario simulates a complete, successful flight operation:
    1. The flight operation state is set to ACTIVATED.
    2. Telemetry data is submitted for a duration of 30 seconds.
    3. The flight operation state is set to ENDED.

    Args:
        client: The FlightBlenderClient instance for API interaction.
        scenario_name: The unique name of the scenario being run.

    Returns:
        A ScenarioResult object containing the results of the scenario execution.
    """
    steps = [
        partial(client.update_operation_state, new_state=OperationState.ACTIVATED),
        partial(client.submit_telemetry, duration_seconds=30),
        partial(client.update_operation_state, new_state=OperationState.ENDED),
    ]

    return run_scenario_template(
        client=client,
        scenario_name=scenario_name,
        flight_declaration_filename="flight-1-bern.json",
        telemetry_filename="flight_1_rid_aircraft_state.json",
        steps=steps,
    )
