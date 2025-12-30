from openutm_verification.core.clients.common.common_client import CommonClient
from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.models import OperationState
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("add_flight_declaration_via_operational_intent")
async def test_add_flight_declaration_via_operational_intent(fb_client: FlightBlenderClient, common_client: CommonClient) -> None:
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

    async with fb_client.create_flight_declaration_via_operational_intent():
        await fb_client.update_operation_state(new_state=OperationState.ACTIVATED, duration_seconds=5)
        await common_client.wait(10)
        await fb_client.update_operation_state(new_state=OperationState.ENDED)
