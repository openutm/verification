from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.execution.config_models import ScenarioId
from openutm_verification.core.reporting.reporting_models import ScenarioResult
from openutm_verification.scenarios.common import get_geo_fence_path
from openutm_verification.scenarios.registry import register_scenario


@register_scenario("geo_fence_upload")
def test_geo_fence_upload(fb_client: FlightBlenderClient) -> ScenarioResult:
    """Upload a geo-fence (Area of Interest) and then delete it (teardown)."""
    fb_client.upload_geo_fence(filename=get_geo_fence_path("geo_fence.geojson"))
    fb_client.get_geo_fence()
