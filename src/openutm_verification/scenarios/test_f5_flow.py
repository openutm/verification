from functools import partial

from openutm_verification.config_models import ScenarioResult
from openutm_verification.flight_blender_client import FlightBlenderClient
from openutm_verification.models import OperationState
from openutm_verification.scenarios.common import run_scenario_template
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("F5_non_conforming_path")
def test_f5_non_conforming_contingent_path(client: FlightBlenderClient, scenario_name: str) -> ScenarioResult:
    steps = [
        partial(client.update_operation_state, new_state=OperationState.ACTIVATED),
        partial(client.submit_telemetry, duration_seconds=20),
        partial(client.check_operation_state_connected, expected_state=OperationState.NONCONFORMING, duration_seconds=5),
        partial(client.update_operation_state, new_state=OperationState.CONTINGENT),
        partial(client.update_operation_state, new_state=OperationState.ENDED),
    ]

    return run_scenario_template(
        client=client,
        scenario_name=scenario_name,
        flight_declaration_filename="flight-1-bern.json",
        telemetry_filename="non-conforming/flight_1_bern_fully_nonconforming.json",
        steps=steps,
    )
