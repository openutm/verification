from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.reporting.reporting_models import ScenarioResult
from openutm_verification.models import OperationState
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("F5_non_conforming_path", setup_flight_declaration=True)
def test_f5_non_conforming_contingent_path(fb_client: FlightBlenderClient) -> ScenarioResult:
    fb_client.update_operation_state(new_state=OperationState.ACTIVATED)
    fb_client.submit_telemetry(duration_seconds=20)
    fb_client.check_operation_state_connected(expected_state=OperationState.NONCONFORMING, duration_seconds=5)
    fb_client.update_operation_state(new_state=OperationState.CONTINGENT)
    fb_client.update_operation_state(new_state=OperationState.ENDED)
