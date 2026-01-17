import asyncio

from loguru import logger

from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.clients.opensky.opensky_client import OpenSkyClient
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("opensky_live_data")
async def test_opensky_live_data(fb_client: FlightBlenderClient, opensky_client: OpenSkyClient) -> None:
    """Fetch live flight data from OpenSky and submit to Flight Blender using template.

    The OpenSky client is provided by the caller; this function focuses on orchestration only.
    """

    # Loop control
    iteration_count = 5  # total number of iterations
    wait_time = 3  # seconds to sleep between iterations

    for i in range(iteration_count):
        logger.info(f"OpenSky iteration {i + 1}/{iteration_count}")

        step_result = await opensky_client.fetch_data()
        observations = step_result.result

        if observations:
            await fb_client.submit_air_traffic(observations=observations)

        if i < iteration_count - 1:
            logger.info(f"Waiting {wait_time} seconds before next iteration...")
            await asyncio.sleep(wait_time)
