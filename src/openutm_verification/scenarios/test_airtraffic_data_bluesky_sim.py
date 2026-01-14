from openutm_verification.core.clients.air_traffic.air_traffic_client import (
    AirTrafficClient,
)
from openutm_verification.core.clients.air_traffic.blue_sky_client import BlueSkyClient
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("bluesky_sim_air_traffic_data")
async def test_bluesky_sim_air_traffic_data(
    fb_client: BlueSkyClient,
    air_traffic_client: AirTrafficClient,
) -> None:
    """Generate simulated air traffic data using OpenSky client based off of BlueSky test
        dataset and submit to Flight Blender using template.

    The OpenSky client is provided by the caller; this function focuses on orchestration only.
    """
    result = await fb_client.generate_bluesky_sim_airtraffic_data()

    print(result)

    observations = result.details
    await fb_client.submit_simulated_air_traffic(observations=observations)
