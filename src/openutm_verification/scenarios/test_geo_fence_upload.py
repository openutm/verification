from functools import partial

from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.execution.config_models import ScenarioId
from openutm_verification.core.reporting.reporting_models import ScenarioResult
from openutm_verification.scenarios.common import get_geo_fence_path, run_scenario_template
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("geo_fence_upload")
def test_geo_fence_upload(fb_client: FlightBlenderClient, scenario_name: ScenarioId) -> ScenarioResult:
    """Upload a geo-fence (Area of Interest) and then delete it (teardown)."""
    steps = [
        partial(fb_client.upload_geo_fence, filename=get_geo_fence_path("geo_fence.geojson")),
        partial(fb_client.get_geo_fence),
    ]

    return run_scenario_template(
        fb_client=fb_client,
        scenario_name=scenario_name,
        steps=steps,
    )
