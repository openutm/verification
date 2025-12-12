from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.execution.config_models import DataFiles
from openutm_verification.models import OperationState
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("F1_flow_no_telemetry_with_user_input")
async def test_f1_no_telemetry_with_user_input(fb_client: FlightBlenderClient, data_files: DataFiles):
    """Runs the F1 no telemetry with user input scenario.

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
    async with fb_client.create_flight_declaration(data_files):
        await fb_client.update_operation_state(new_state=OperationState.ACTIVATED)
        await fb_client.wait_for_user_input(prompt="Press Enter to end the operation...")
        await fb_client.update_operation_state(new_state=OperationState.ENDED)
    await fb_client.teardown_flight_declaration()
