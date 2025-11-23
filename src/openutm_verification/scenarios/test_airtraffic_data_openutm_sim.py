from openutm_verification.core.clients.air_traffic.air_traffic_client import (
    AirTrafficClient,
)
from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("openutm_sim_air_traffic_data")
def test_openutm_sim_air_traffic_data(
    fb_client: FlightBlenderClient,
    air_traffic_client: AirTrafficClient,
) -> ScenarioResult:
    """Generate simulated air traffic data using OpenSky client and submit to Flight Blender using template.

    The OpenSky client is provided by the caller; this function focuses on orchestration only.
    """
    step_result = air_traffic_client.generate_simulated_air_traffic_data()
    observations = step_result.details
    fb_client.submit_simulated_air_traffic(observations=observations)
