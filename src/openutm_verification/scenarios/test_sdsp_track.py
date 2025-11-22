import uuid

from loguru import logger

from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.reporting.reporting_models import ScenarioResult
from openutm_verification.models import SDSPSessionAction
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("sdsp_track")
def sdsp_track(fb_client: FlightBlenderClient, scenario_name: str) -> ScenarioResult:
    """Runs the SDSP track scenario.
    This scenario
    """
    session_id = str(uuid.uuid4())
    logger.info(f"Starting SDSP track scenario with session ID: {session_id}")

    fb_client.start_stop_sdsp_session(
        action=SDSPSessionAction.START,
        session_id=session_id,
    )
    # Wait for some time to simulate track period
    fb_client.wait_x_seconds(wait_time_seconds=2)

    fb_client.initialize_verify_sdsp_track(
        session_id=session_id,
        expected_heartbeat_interval_seconds=1,
        expected_heartbeat_count=3,
    )

    fb_client.wait_x_seconds(wait_time_seconds=5)

    fb_client.start_stop_sdsp_session(
        action=SDSPSessionAction.STOP,
        session_id=session_id,
    )
