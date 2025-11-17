from functools import partial

from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.execution.config_models import ScenarioId
from openutm_verification.core.reporting.reporting_models import ScenarioResult
from openutm_verification.models import OperationState
from openutm_verification.scenarios.common import run_scenario_template
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("F1_happy_path")
def test_f1_happy_path(fb_client: FlightBlenderClient, scenario_id: ScenarioId) -> ScenarioResult:
    """Runs the F1 happy path scenario.

    This scenario simulates a complete, successful flight operation:
    1. The flight operation state is set to ACTIVATED.
    2. Telemetry data is submitted for a duration of 30 seconds.
    3. The flight operation state is set to ENDED.

    Args:
        fb_client: The FlightBlenderClient instance for API interaction.
        scenario_id: The unique name of the scenario being run.

    Returns:
        A ScenarioResult object containing the results of the scenario execution.
    """
    steps = [
        partial(fb_client.update_operation_state, new_state=OperationState.ACTIVATED),
        partial(fb_client.submit_telemetry, duration_seconds=30),
        partial(fb_client.update_operation_state, new_state=OperationState.ENDED),
    ]

    return run_scenario_template(
        fb_client=fb_client,
        scenario_id=scenario_id,
        steps=steps,
    )
