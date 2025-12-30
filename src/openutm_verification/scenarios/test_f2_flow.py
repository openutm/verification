from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.models import OperationState
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("F2_contingent_path")
async def test_f2_contingent_path(fb_client: FlightBlenderClient):
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
    async with fb_client.create_flight_declaration():
        await fb_client.update_operation_state(state=OperationState.ACTIVATED)
        await fb_client.submit_telemetry(duration=10)
        await fb_client.update_operation_state(state=OperationState.CONTINGENT, duration=7)
        await fb_client.update_operation_state(state=OperationState.ENDED)

    await fb_client.teardown_flight_declaration()
