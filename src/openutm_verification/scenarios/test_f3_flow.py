from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.execution.config_models import DataFiles
from openutm_verification.models import OperationState
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("F3_non_conforming_path")
def test_f3_non_conforming_path(fb_client: FlightBlenderClient, data_files: DataFiles):
    """Runs the F3 non-conforming path scenario.

    This scenario simulates a flight that deviates from its declared flight plan,
    triggering a NONCONFORMING state.
    1. The flight operation state is set to ACTIVATED.
    2. Non-conforming telemetry is submitted for 20 seconds.
    3. The operation state is checked to ensure it has become NONCONFORMING.
    4. The flight operation state is set to ENDED.

    Args:
        fb_client: The FlightBlenderClient instance for API interaction.
        data_files: The DataFiles instance containing file paths for telemetry, flight declaration, and geo-fence.

    Returns:
        A ScenarioResult object containing the results of the scenario execution.
    """
    with fb_client.flight_declaration(data_files):
        fb_client.update_operation_state(new_state=OperationState.ACTIVATED)
        fb_client.submit_telemetry(duration_seconds=20)
        fb_client.check_operation_state(expected_state=OperationState.NONCONFORMING, duration_seconds=5)
        fb_client.update_operation_state(new_state=OperationState.ENDED)
