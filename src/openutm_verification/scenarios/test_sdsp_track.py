import asyncio
import uuid

from loguru import logger

from openutm_verification.core.clients.air_traffic.air_traffic_client import AirTrafficClient
from openutm_verification.core.clients.common.common_client import CommonClient
from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.models import SDSPSessionAction
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("sdsp_track")
async def sdsp_track(fb_client: FlightBlenderClient, air_traffic_client: AirTrafficClient, common_client: CommonClient) -> None:
    """Runs the SDSP track scenario.
    This scenario
    """
    session_id = str(uuid.uuid4())
    logger.info(f"Starting SDSP track scenario with session ID: {session_id}")

    await fb_client.start_stop_sdsp_session(
        action=SDSPSessionAction.START,
        session_id=session_id,
    )

    observations = (await air_traffic_client.generate_simulated_air_traffic_data()).result
    # to start a background parallel task, instead of await, use create_task:
    task = asyncio.create_task(fb_client.submit_simulated_air_traffic(observations=observations))
    # Task is now running, concurrently while any other `async await` calls are done.
    # Wait for some time to simulate track period
    await common_client.wait(duration=2)

    await fb_client.initialize_verify_sdsp_track(
        session_id=session_id,
        expected_track_interval_seconds=1,
        expected_track_count=3,
    )

    await common_client.wait(duration=5)

    await fb_client.start_stop_sdsp_session(
        action=SDSPSessionAction.STOP,
        session_id=session_id,
    )

    # task.cancel()  # Cancel the background task if still running
    await task  # Wait for the task to complete
