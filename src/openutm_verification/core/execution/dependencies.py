from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Coroutine,
    Generator,
    Iterable,
    TypeVar,
    cast,
)

from loguru import logger

from openutm_verification.auth.providers import get_auth_provider
from openutm_verification.core.clients.air_traffic.air_traffic_client import (
    AirTrafficClient,
)
from openutm_verification.core.clients.air_traffic.base_client import (
    create_air_traffic_settings,
)
from openutm_verification.core.clients.air_traffic.blue_sky_client import (
    BlueSkyClient,
)
from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.clients.opensky.base_client import (
    create_opensky_settings,
)
from openutm_verification.core.clients.opensky.opensky_client import OpenSkyClient
from openutm_verification.core.execution.config_models import (
    AppConfig,
    DataFiles,
    ScenarioId,
    get_settings,
)
from openutm_verification.core.execution.dependency_resolution import (
    CONTEXT,
    dependency,
)
from openutm_verification.core.reporting.reporting_models import ScenarioResult
from openutm_verification.scenarios.registry import SCENARIO_REGISTRY

T = TypeVar("T")


def get_scenario_docs(scenario_id: str) -> str | None:
    docs_path = SCENARIO_REGISTRY[scenario_id].get("docs")
    if docs_path and docs_path.exists():
        try:
            return docs_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to read docs file {docs_path}: {e}")
    else:
        logger.warning(f"Docs file not found: {docs_path}")
        return None


def scenarios() -> Iterable[tuple[str, Callable[..., Coroutine[Any, Any, ScenarioResult]]]]:
    """Provides scenarios to run with their functions.

    Returns:
        An iterable of tuples containing (scenario_id, scenario_function).
    """
    config = get_settings()

    scenarios_to_iterate = []

    # Determine which suites to run
    target_suite_names = config.target_suites if config.target_suites else config.suites.keys()

    if not target_suite_names:
        logger.warning("No suites defined in configuration.")

    for suite_name in target_suite_names:
        if suite_name not in config.suites:
            logger.error(f"Target suite '{suite_name}' not found in configuration.")
            continue

        suite = config.suites[suite_name]
        scenarios_list = suite.scenarios or []
        logger.info(f"Adding suite: {suite_name} with {len(scenarios_list)} scenarios.")
        for suite_scenario in scenarios_list:
            scenarios_to_iterate.append((suite_name, suite_scenario))

    for suite_name, item in scenarios_to_iterate:
        scenario_id = item.name
        suite_scenario = item

        if scenario_id in SCENARIO_REGISTRY:
            logger.info("=" * 100)
            logger.info(f"Running scenario: {scenario_id}")

            scenario_func = SCENARIO_REGISTRY[scenario_id].get("func")
            docs_content = get_scenario_docs(scenario_id)

            CONTEXT.set(
                {
                    "scenario_id": scenario_id,
                    "suite_scenario": suite_scenario,
                    "suite_name": suite_name,
                    "docs": docs_content,
                }
            )
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

    # Check for suite override
    suite_scenario = CONTEXT.get().get("suite_scenario")

    if suite_scenario:
        # Merge suite overrides with base config
        trajectory = suite_scenario.trajectory or config.data_files.trajectory
        flight_declaration = suite_scenario.flight_declaration or config.data_files.flight_declaration
        flight_declaration_via_operational_intent = (
            suite_scenario.flight_declaration_via_operational_intent or config.data_files.flight_declaration_via_operational_intent
        )
        geo_fence = suite_scenario.geo_fence or config.data_files.geo_fence
    else:
        # Use base config
        trajectory = config.data_files.trajectory
        flight_declaration = config.data_files.flight_declaration
        geo_fence = config.data_files.geo_fence

    data = DataFiles(
        trajectory=trajectory,
        flight_declaration=flight_declaration,
        flight_declaration_via_operational_intent=flight_declaration_via_operational_intent,
        geo_fence=geo_fence,
    )
    yield data


@dependency(AppConfig)
def app_config() -> Generator[AppConfig, None, None]:
    """Provides the application configuration for dependency injection.

    Returns:
        An instance of AppConfig.
    """
    yield cast(AppConfig, get_settings())


@dependency(FlightBlenderClient)
async def flight_blender_client(
    config: AppConfig,
) -> AsyncGenerator[FlightBlenderClient, None]:
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
    async with FlightBlenderClient(base_url=config.flight_blender.url, credentials=credentials) as fb_client:
        yield fb_client


@dependency(OpenSkyClient)
async def opensky_client(config: AppConfig) -> AsyncGenerator[OpenSkyClient, None]:
    """Provides an OpenSkyClient instance for dependency injection."""
    settings = create_opensky_settings()
    async with OpenSkyClient(settings) as opensky_client:
        yield opensky_client


@dependency(AirTrafficClient)
async def air_traffic_client(
    config: AppConfig,
) -> AsyncGenerator[AirTrafficClient, None]:
    """Provides an AirTrafficClient instance for dependency injection."""
    settings = create_air_traffic_settings()
    async with AirTrafficClient(settings) as air_traffic_client:
        yield air_traffic_client


@dependency(BlueSkyClient)
async def bluesky_client(
    config: AppConfig,
) -> AsyncGenerator[BlueSkyClient, None]:
    """Provides a BlueSkyClient instance for dependency injection."""
    settings = create_air_traffic_settings()
    async with BlueSkyClient(settings) as bluesky_client:
        yield bluesky_client
