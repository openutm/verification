from functools import partial

from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.execution.config_models import ScenarioId
from openutm_verification.core.reporting.reporting_models import ScenarioResult
from openutm_verification.models import OperationState
from openutm_verification.scenarios.common import run_scenario_template
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("add_flight_declaration")
def test_add_flight_declaration(fb_client: FlightBlenderClient, scenario_name: ScenarioId) -> ScenarioResult:
    """Runs the add flight declaration scenario.

    This scenario replicates the behavior of the add_flight_declaration.py importer:
    1. Upload flight declaration (handled by template).
    2. Wait 20 seconds.
    3. Set flight operation state to ACTIVATED.
    4. Submit telemetry data for 30 seconds.
    5. Set flight operation state to ENDED.

    Args:
        fb_client: The FlightBlenderClient instance for API interaction.
        scenario_name: The unique name of the scenario being run.

    Returns:
        A ScenarioResult object containing the results of the scenario execution.
    """
    steps = [
        partial(fb_client.update_operation_state, new_state=OperationState.ACTIVATED, duration_seconds=20),
        partial(fb_client.submit_telemetry, duration_seconds=30),
        partial(fb_client.update_operation_state, new_state=OperationState.ENDED),
    ]

    return run_scenario_template(
        fb_client=fb_client,
        scenario_name=scenario_name,
        steps=steps,
    )
