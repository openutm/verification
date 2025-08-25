from pathlib import Path

from openutm_verification.flight_blender_client import FlightBlenderClient
from openutm_verification.models import OperationState


def run_f3_scenario(client: FlightBlenderClient) -> dict:
    """
    Runs the F3 scenario: Non-Conforming Path.
    """
    scenario_name = "F3 Non-Conforming Path"
    parent_dir = Path(__file__).parent.resolve()
    flight_declaration_path = parent_dir / "../assets/flight_declarations_samples/flight-1-bern.json"
    telemetry_path = parent_dir / "../assets/rid_samples/non-conforming/flight_1_bern_fully_nonconforming.json"

    upload_result = client.upload_flight_declaration(filename=str(flight_declaration_path))
    flight_declaration_id = upload_result["details"]["id"]

    steps = [
        upload_result,
        client.update_operation_state(operation_id=flight_declaration_id, new_state=OperationState.ACTIVATED),
        client.submit_telemetry(str(telemetry_path), flight_declaration_id, duration_seconds=20),
        client.check_operation_state(operation_id=flight_declaration_id, expected_state=OperationState.NONCONFORMING, duration_seconds=5),
        client.update_operation_state(operation_id=flight_declaration_id, new_state=OperationState.ENDED),
    ]

    return {
        "name": scenario_name,
        "status": "PASS" if all(step["status"] == "PASS" for step in steps) else "FAIL",
        "duration_seconds": sum(step["duration"] for step in steps),
        "steps": steps,
    }
