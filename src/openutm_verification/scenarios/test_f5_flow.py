from functools import partial

from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.reporting.reporting_models import ScenarioResult
from openutm_verification.models import OperationState
from openutm_verification.scenarios.common import run_scenario_template
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("F5_non_conforming_path")
def test_f5_non_conforming_contingent_path(fb_client: FlightBlenderClient, scenario_name: ScenarioId) -> ScenarioResult:
    steps = [
        partial(fb_client.update_operation_state, new_state=OperationState.ACTIVATED),
        partial(fb_client.submit_telemetry, duration_seconds=20),
        partial(fb_client.check_operation_state_connected, expected_state=OperationState.NONCONFORMING, duration_seconds=5),
        partial(fb_client.update_operation_state, new_state=OperationState.CONTINGENT),
        partial(fb_client.update_operation_state, new_state=OperationState.ENDED),
    ]

    return run_scenario_template(
        fb_client=fb_client,
        scenario_name=scenario_name,
        steps=steps,
    )
