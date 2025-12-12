from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.execution.config_models import DataFiles
from openutm_verification.models import OperationState
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("F5_non_conforming_path")
async def test_f5_non_conforming_contingent_path(fb_client: FlightBlenderClient, data_files: DataFiles) -> None:
    async with fb_client.create_flight_declaration(data_files):
        await fb_client.update_operation_state(new_state=OperationState.ACTIVATED)
        await fb_client.submit_telemetry(duration_seconds=20)
        await fb_client.check_operation_state_connected(expected_state=OperationState.NONCONFORMING, duration_seconds=5)
        await fb_client.update_operation_state(new_state=OperationState.CONTINGENT)
        await fb_client.update_operation_state(new_state=OperationState.ENDED)
    
    fb_client.teardown_flight_declaration()
