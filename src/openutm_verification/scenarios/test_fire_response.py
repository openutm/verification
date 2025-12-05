from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.execution.config_models import DataFiles
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("fire_response")
def test_fire_response(fb_client: FlightBlenderClient, data_files: DataFiles) -> None:
    """Runs the Fire Response scenario."""
    pass
