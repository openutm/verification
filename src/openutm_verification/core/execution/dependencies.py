import base64
import mimetypes
import re
from pathlib import Path
from typing import Callable, Generator, Iterable, TypeVar

from loguru import logger

from openutm_verification.auth.providers import get_auth_provider
from openutm_verification.core.clients.air_traffic.air_traffic_client import AirTrafficClient
from openutm_verification.core.clients.air_traffic.base_client import create_air_traffic_settings
from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.clients.opensky.base_client import create_opensky_settings
from openutm_verification.core.clients.opensky.opensky_client import OpenSkyClient
from openutm_verification.core.execution.config_models import AppConfig, DataFiles, ScenarioId, get_settings
from openutm_verification.core.execution.dependency_resolution import CONTEXT, dependency
from openutm_verification.core.reporting.reporting_models import ScenarioResult
from openutm_verification.scenarios.registry import SCENARIO_REGISTRY

T = TypeVar("T")


def embed_images(content: str, base_path: Path) -> str:
    """
    Embeds images referenced in markdown content as base64 data URIs.
    Handles both markdown image syntax ![alt](path) and HTML <img src="path">.
    """

    def replace_image(match):
        alt_text = match.group(1)
        image_path_str = match.group(2)

        # Ignore if already a data URI or absolute URL
        if image_path_str.startswith(("data:", "http:", "https:")):
            return match.group(0)

        image_path = base_path / image_path_str
        if image_path.exists():
            try:
                mime_type, _ = mimetypes.guess_type(image_path)
                if not mime_type:
                    mime_type = "image/png"

                with open(image_path, "rb") as img_file:
                    encoded_string = base64.b64encode(img_file.read()).decode("utf-8")

                return f"![{alt_text}](data:{mime_type};base64,{encoded_string})"
            except Exception as e:
                logger.warning(f"Failed to embed image {image_path}: {e}")
                return match.group(0)
        else:
            logger.warning(f"Image not found: {image_path}")
            return match.group(0)

    def replace_html_image(match):
        full_tag = match.group(0)
        src_match = re.search(r'src=["\'](.*?)["\']', full_tag)
        if not src_match:
            return full_tag

        image_path_str = src_match.group(1)

        if image_path_str.startswith(("data:", "http:", "https:")):
            return full_tag

        image_path = base_path / image_path_str
        if image_path.exists():
            try:
                mime_type, _ = mimetypes.guess_type(image_path)
                if not mime_type:
                    mime_type = "image/png"

                with open(image_path, "rb") as img_file:
                    encoded_string = base64.b64encode(img_file.read()).decode("utf-8")

                new_src = f"data:{mime_type};base64,{encoded_string}"
                return full_tag.replace(image_path_str, new_src)
            except Exception as e:
                logger.warning(f"Failed to embed HTML image {image_path}: {e}")
                return full_tag
        else:
            logger.warning(f"HTML Image not found: {image_path}")
            return full_tag

    # Replace Markdown images
    content = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_image, content)

    # Replace HTML images
    content = re.sub(r'<img\s+[^>]*src=["\'][^"\']*["\'][^>]*>', replace_html_image, content)

    return content


def get_scenario_docs(scenario_id: str) -> None | str:
    docs_path = SCENARIO_REGISTRY[scenario_id].get("docs")
    if docs_path and docs_path.exists():
        try:
            content = docs_path.read_text(encoding="utf-8")
            return embed_images(content, docs_path.parent)
        except Exception as e:
            logger.warning(f"Failed to read docs file {docs_path}: {e}")
    else:
        logger.warning(f"Docs file not found: {docs_path}")


def scenarios() -> Iterable[tuple[str, Callable[..., ScenarioResult]]]:
    """Provides scenarios to run with their functions.

    Returns:
        An iterable of tuples containing (scenario_id, scenario_function).
    """
    scenarios_to_run = get_settings().scenarios
    logger.info(f"Found {len(scenarios_to_run)} scenarios to run.")

    for scenario_id in scenarios_to_run:
        if scenario_id in SCENARIO_REGISTRY:
            logger.info("=" * 100)
            logger.info(f"Running scenario: {scenario_id}")
            docs_content = get_scenario_docs(scenario_id)

            CONTEXT.set({"scenario_id": scenario_id, "docs": docs_content})
            yield scenario_id, SCENARIO_REGISTRY[scenario_id]["func"]
        else:
            logger.warning(f"Scenario {scenario_id} not found in registry.")
    logger.info("=" * 100)


@dependency(ScenarioId)
def scenario_id() -> Generator[ScenarioId, None, None]:
    """Provides a ScenarioId for dependency injection.

    Returns:
        The current scenario identifier.
    """
    yield CONTEXT.get()["scenario_id"]


@dependency(DataFiles)
def data_files(scenario_id: ScenarioId) -> Generator[DataFiles, None, None]:
    """Provides data files configuration for dependency injection.

    Returns:
        An instance of DataFiles.
    """
    config = get_settings()
    scenario_config = config.scenarios.get(scenario_id) or config.data_files
    data = DataFiles(
        telemetry=scenario_config.telemetry or config.data_files.telemetry,
        flight_declaration=scenario_config.flight_declaration or config.data_files.flight_declaration,
        geo_fence=scenario_config.geo_fence or config.data_files.geo_fence,
    )
    yield data


@dependency(AppConfig)
def app_config() -> Generator[AppConfig, None, None]:
    """Provides the application configuration for dependency injection.

    Returns:
        An instance of AppConfig.
    """
    yield get_settings()


@dependency(FlightBlenderClient)
def flight_blender_client(config: AppConfig) -> Generator[FlightBlenderClient, None, None]:
    """Provides a FlightBlenderClient instance for dependency injection.

    Args:
        config: The application configuration containing Flight Blender settings.
    Returns:
        An instance of FlightBlenderClient.
    """
    auth_provider = get_auth_provider(config.flight_blender.auth)
    credentials = auth_provider.get_cached_credentials(
        audience=config.flight_blender.auth.audience or "",
        scopes=config.flight_blender.auth.scopes or [],
    )
    with FlightBlenderClient(base_url=config.flight_blender.url, credentials=credentials) as fb_client:
        yield fb_client


@dependency(OpenSkyClient)
def opensky_client(config: AppConfig) -> Generator[OpenSkyClient, None, None]:
    """Provides an OpenSkyClient instance for dependency injection."""
    settings = create_opensky_settings()
    with OpenSkyClient(settings) as opensky_client:
        yield opensky_client


@dependency(AirTrafficClient)
def air_traffic_client(config: AppConfig) -> Generator[AirTrafficClient, None, None]:
    """Provides an AirTrafficClient instance for dependency injection."""
    settings = create_air_traffic_settings()
    with AirTrafficClient(settings) as air_traffic_client:
        yield air_traffic_client
