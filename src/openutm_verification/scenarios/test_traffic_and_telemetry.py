import asyncio

from loguru import logger

from openutm_verification.core.clients.air_traffic.blue_sky_client import BlueSkyClient
from openutm_verification.core.clients.amqp import AMQPClient
from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.models import OperationState
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("traffic_and_telemetry_sim")
async def traffic_and_telemetry_sim(
    fb_client: FlightBlenderClient,
    blue_sky_client: BlueSkyClient,
    amqp_client: AMQPClient,
) -> None:
    """Runs a scenario with simulated air traffic and drone telemetry concurrently.

    This scenario also monitors AMQP events for operational messages
    related to the flight declaration.
    """
    logger.info("Starting Traffic and Telemetry simulation scenario")

    # Check AMQP connection (optional, will log warning if not configured)
    connection_result = await amqp_client.check_connection()
    connection_status = connection_result.result or {}
    if connection_status.get("connected"):
        logger.info(f"AMQP connected to {connection_status.get('url_host')}")
    else:
        logger.warning(f"AMQP not available: {connection_status.get('error')}")

    # Explicit cleanup before starting
    await fb_client.cleanup_flight_declarations()

    # Setup Flight Declaration
    async with fb_client.create_flight_declaration():
        # Get the flight declaration ID for AMQP routing key
        flight_declaration_id = fb_client.latest_flight_declaration_id

        # Start AMQP monitoring for flight events (background)
        amqp_task = None
        if connection_status.get("connected") and flight_declaration_id:
            amqp_task = asyncio.create_task(amqp_client.start_queue_monitor(routing_key=flight_declaration_id, duration=60))
            logger.info(f"AMQP queue monitor started for flight declaration {flight_declaration_id}")

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

        # Stop AMQP monitoring and get collected messages
        if amqp_task:
            await amqp_client.stop_queue_monitor()
            messages_result = await amqp_client.get_received_messages(routing_key_filter=flight_declaration_id)
            messages = messages_result.result or []
            logger.info(f"Collected {len(messages)} AMQP messages for flight declaration")
            for msg in messages:
                logger.debug(f"AMQP message: {msg}")

    await fb_client.teardown_flight_declaration()
