import time
from functools import partial

from loguru import logger

from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.clients.opensky.opensky_client import OpenSkyClient
from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.core.reporting.reporting_models import ScenarioResult, Status
from openutm_verification.scenarios.common import run_air_traffic_scenario_template
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("airtraffic_live_data")
def test_airtraffic_live_data(fb_client: FlightBlenderClient, scenario_name: str) -> ScenarioResult:
    """This test creates a sample data set of airtraffic data and submits it to Flight Blender using"""

    aggregated_steps = []
    overall_status = Status.PASS
    total_duration = 30.0

    steps = [
        partial(fb_client.generate_air_traffic),
        partial(fb_client.submit_air_traffic),
    ]

    result = run_air_traffic_scenario_template(
        fb_client=fb_client,
        scenario_name=f"{scenario_name} - Generate and Submit Airtraffic Data",
        steps=steps,
    )

    aggregated_steps.extend(result.steps)
    total_duration += result.duration_seconds
    if result.status == Status.FAIL:
        overall_status = Status.FAIL

    return ScenarioResult(
        name=scenario_name,
        status=overall_status,
        duration_seconds=total_duration,
        steps=aggregated_steps,
    )
