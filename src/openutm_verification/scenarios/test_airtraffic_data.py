import time
from functools import partial

from loguru import logger

from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.clients.opensky.opensky_client import OpenSkyClient
from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.core.reporting.reporting_models import ScenarioResult, Status
from openutm_verification.scenarios.common import run_scenario_template
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("airtraffic_live_data")
def test_airtraffic_live_data(fb_client: FlightBlenderClient, opensky_client: OpenSkyClient, scenario_name: str) -> ScenarioResult:
    """ This test creates a sample data set of airtraffic data and submits it to Flight Blender using """


    aggregated_steps = []
    overall_status = Status.PASS
    total_duration = 30.0


    steps = [
        partial(opensky_client.generate_airtraffic),
        partial(fb_client.submit_air_traffic),
    ]

    result = run_scenario_template(
        fb_client=fb_client,
        opensky_client=opensky_client,
        scenario_name=f"{scenario_name} (iter {i + 1})",
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
