from functools import partial

from openutm_verification.config_models import ScenarioResult
from openutm_verification.flight_blender_client import FlightBlenderClient
from openutm_verification.models import OperationState
from tests.scenarios.common import run_scenario_template
from tests.scenarios.registry import register_scenario


@register_scenario("F3_non_conforming_path")
def test_f3_non_conforming_path(client: FlightBlenderClient, scenario_name: str) -> ScenarioResult:
    """Runs the F3 non-conforming path scenario.

    This scenario simulates a flight that deviates from its declared flight plan,
    triggering a NONCONFORMING state.
    1. The flight operation state is set to ACTIVATED.
    2. Non-conforming telemetry is submitted for 20 seconds.
    3. The operation state is checked to ensure it has become NONCONFORMING.
    4. The flight operation state is set to ENDED.

    Args:
        client: The FlightBlenderClient instance for API interaction.
        scenario_name: The unique name of the scenario being run.

    Returns:
        A ScenarioResult object containing the results of the scenario execution.
    """
    steps = [
        partial(client.update_operation_state, new_state=OperationState.ACTIVATED),
        partial(client.submit_telemetry, duration_seconds=20),
        partial(client.check_operation_state, expected_state=OperationState.NONCONFORMING, duration_seconds=5),
        partial(client.update_operation_state, new_state=OperationState.ENDED),
    ]

    return run_scenario_template(
        client=client,
        scenario_name=scenario_name,
        flight_declaration_filename="flight-1-bern.json",
        telemetry_filename="non-conforming/flight_1_bern_fully_nonconforming.json",
        steps=steps,
    )
