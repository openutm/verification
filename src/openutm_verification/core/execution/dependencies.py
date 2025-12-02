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


def scenarios() -> Iterable[tuple[str, Callable[..., ScenarioResult]]]:
    """Provides scenarios to run with their functions.

    Returns:
        An iterable of tuples containing (scenario_id, scenario_function).
    """
    scenarios_to_run = get_settings().scenarios
    logger.info(f"Found {len(scenarios_to_run)} scenarios to run.")
    for scenario_id in scenarios_to_run:
        CONTEXT.set({"scenario_id": scenario_id})
        if scenario_id in SCENARIO_REGISTRY:
            logger.info("=" * 100)
            logger.info(f"Running scenario: {scenario_id}")
            scenario_func = SCENARIO_REGISTRY[scenario_id]
            yield scenario_id, scenario_func
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
        trajectory=scenario_config.trajectory or config.data_files.trajectory,
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
