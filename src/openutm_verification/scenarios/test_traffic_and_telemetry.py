import asyncio

from loguru import logger

from openutm_verification.core.clients.air_traffic.blue_sky_client import BlueSkyClient
from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.models import OperationState
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("traffic_and_telemetry_sim")
async def traffic_and_telemetry_sim(
    fb_client: FlightBlenderClient,
    blue_sky_client: BlueSkyClient,
) -> None:
    """Runs a scenario with simulated air traffic and drone telemetry concurrently."""
    logger.info("Starting Traffic and Telemetry simulation scenario")

    # Explicit cleanup before starting
    await fb_client.cleanup_flight_declarations()

    # Setup Flight Declaration
    async with fb_client.create_flight_declaration():
        # Activate Operation
        await fb_client.update_operation_state(OperationState.ACTIVATED)

        # Generate BlueSky Simulation Air Traffic Data
        # Run traffic for 35 seconds to allow for 5s start delay + 30s telemetry overlap
        result = await blue_sky_client.generate_bluesky_sim_air_traffic_data(duration=35)
        observations = result.result
        logger.info(f"Generated {len(observations)} observations from BlueSky simulation")

        # Start Submit Simulated Air Traffic (background)
        traffic_task = asyncio.create_task(fb_client.submit_simulated_air_traffic(observations=observations))

        logger.info("Traffic submission started, waiting 5 seconds before starting telemetry...")
        await asyncio.sleep(5)

        # Start Submit Telemetry (background)
        telemetry_task = asyncio.create_task(fb_client.submit_telemetry(duration=30))

        logger.info("Waiting for telemetry submission to complete...")
        await telemetry_task

        logger.info("Waiting for traffic submission to complete...")
        await traffic_task

        # End Operation
        await fb_client.update_operation_state(OperationState.ENDED)

    await fb_client.teardown_flight_declaration()
