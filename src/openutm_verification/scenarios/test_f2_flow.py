from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.execution.config_models import DataFiles
from openutm_verification.models import OperationState
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("F2_contingent_path")
def test_f2_contingent_path(fb_client: FlightBlenderClient, data_files: DataFiles):
    """Runs the F2 contingent path scenario.

    This scenario simulates a flight operation that enters a contingent state:
    1. The flight operation state is set to ACTIVATED.
    2. Telemetry data is submitted for 10 seconds.
    3. The flight operation state is updated to CONTINGENT and held for 7 seconds.
    4. The flight operation state is set to ENDED.

    Args:
        fb_client: The FlightBlenderClient instance for API interaction.
        scenario_id: The unique name of the scenario being run.

    Returns:
        A ScenarioResult object containing the results of the scenario execution.
    """
    with fb_client.flight_declaration(data_files):
        fb_client.update_operation_state(new_state=OperationState.ACTIVATED)
        fb_client.submit_telemetry(duration_seconds=10)
        fb_client.update_operation_state(new_state=OperationState.CONTINGENT, duration_seconds=7)
        fb_client.update_operation_state(new_state=OperationState.ENDED)
