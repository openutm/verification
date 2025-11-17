import uuid
from functools import partial

from loguru import logger

from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.execution.config_models import ScenarioId
from openutm_verification.core.reporting.reporting_models import ScenarioResult
from openutm_verification.models import SDSPSessionAction
from openutm_verification.scenarios.common import run_sdsp_scenario_template
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("sdsp_track_heartbeat")
def sdsp_track_heartbeat(fb_client: FlightBlenderClient, scenario_id: ScenarioId) -> ScenarioResult:
    """Runs the SDSP heartbeat scenario.
    This scenario
    """
    session_id = str(uuid.uuid4())
    logger.info(f"Starting SDSP heartbeat scenario with session ID: {session_id}")
    steps = [
        partial(
            fb_client.start_stop_sdsp_session,
            action=SDSPSessionAction.START,
            session_id=session_id,
        ),
        # Wait for some time to simulate heartbeat period
        partial(fb_client.wait_x_seconds, wait_time_seconds=2),
        partial(
            fb_client.initialize_verify_sdsp_heartbeat,
            session_id=session_id,
            expected_heartbeat_interval_seconds=1,
            expected_heartbeat_count=3,
        ),
        partial(
            fb_client.wait_x_seconds,
            wait_time_seconds=5,
        ),
        partial(
            fb_client.start_stop_sdsp_session,
            action=SDSPSessionAction.STOP,
            session_id=session_id,
        ),
    ]

    return run_sdsp_scenario_template(
        fb_client=fb_client,
        scenario_id=scenario_id,
        steps=steps,
    )
