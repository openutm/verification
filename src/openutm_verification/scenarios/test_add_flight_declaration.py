from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.execution.config_models import DataFiles
from openutm_verification.models import OperationState
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("add_flight_declaration")
def test_add_flight_declaration(fb_client: FlightBlenderClient, data_files: DataFiles) -> None:
    """Runs the add flight declaration scenario.

    This scenario replicates the behavior of the add_flight_declaration.py importer:
    1. Upload flight declaration (handled by template).
    2. Wait 20 seconds.
    3. Set flight operation state to ACTIVATED.
    4. Submit telemetry data for 30 seconds.
    5. Set flight operation state to ENDED.

    Args:
        fb_client: The FlightBlenderClient instance for API interaction.
        data_files: The DataFiles instance containing file paths for telemetry, flight declaration, and geo-fence.

    Returns:
        A ScenarioResult object containing the results of the scenario execution.
    """
    with fb_client.flight_declaration(data_files):
        fb_client.update_operation_state(new_state=OperationState.ACTIVATED, duration_seconds=20)
        fb_client.submit_telemetry(duration_seconds=30)
        fb_client.update_operation_state(new_state=OperationState.ENDED)
