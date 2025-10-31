from functools import partial

from openutm_verification.core.clients.air_traffic.air_traffic_client import (
    AirTrafficClient,
)
from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.reporting.reporting_models import ScenarioResult
from openutm_verification.scenarios.common import run_air_traffic_scenario_template
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("openutm_sim_air_traffic_data")
def test_openutm_sim_air_traffic_data(
    fb_client: FlightBlenderClient,
    air_traffic_client: AirTrafficClient,
    scenario_name: str,
) -> ScenarioResult:
    """Generate simulated air traffic data using OpenSky client and submit to Flight Blender using template.

    The OpenSky client is provided by the caller; this function focuses on orchestration only.
    """

    steps = [
        partial(air_traffic_client.generate_simulated_air_traffic_data),
        partial(fb_client.submit_air_traffic),
    ]

    return run_air_traffic_scenario_template(
        fb_client=fb_client,
        air_traffic_client=air_traffic_client,
        scenario_name=scenario_name,
        steps=steps,
    )
