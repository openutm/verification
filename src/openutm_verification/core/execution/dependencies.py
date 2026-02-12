from typing import (
    AsyncGenerator,
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
    AirTrafficSettings,
    BayesianAirTrafficSettings,
    BlueSkyAirTrafficSettings,
)
from openutm_verification.core.clients.air_traffic.bayesian_air_traffic_client import (
    BayesianTrafficClient,
)
from openutm_verification.core.clients.air_traffic.blue_sky_client import (
    BlueSkyClient,
)
from openutm_verification.core.clients.amqp import (
    AMQPClient,
    AMQPSettings,
)
from openutm_verification.core.clients.common.common_client import CommonClient
from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.clients.opensky.base_client import (
    OpenSkySettings,
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
from openutm_verification.core.steps.air_traffic_step import AirTrafficStepClient
from openutm_verification.server.runner import SessionManager
from openutm_verification.utils.paths import get_docs_directory

T = TypeVar("T")


def get_scenario_docs(scenario_id: str) -> str | None:
    docs_dir = get_docs_directory()
    if not docs_dir:
        return None

    docs_path = docs_dir / f"{scenario_id}.md"
    if not docs_path.exists():
        return None

    try:
        return docs_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Failed to read docs file {docs_path}: {e}")
        return None


def scenarios() -> Iterable[str]:
    """Provides scenario IDs to run (YAML-only)."""
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

        logger.info("=" * 100)
        logger.info(f"Running YAML scenario: {scenario_id}")

        docs_content = get_scenario_docs(scenario_id)

        CONTEXT.set(
            {
                "scenario_id": scenario_id,
                "suite_scenario": suite_scenario,
                "suite_name": suite_name,
                "docs": docs_content,
            }
        )
        yield scenario_id
    logger.info("=" * 100)


@dependency(ScenarioId)
def scenario_id() -> Generator[ScenarioId, None, None]:
    """Provides a ScenarioId for dependency injection.

    Returns:
        The current scenario identifier.
    """
    yield CONTEXT.get()["scenario_id"]


@dependency(DataFiles)
def data_files() -> Generator[DataFiles, None, None]:
    """Provides data files configuration for dependency injection.

    Returns the SuiteScenario from context (which already has defaults merged at config load time),
    or falls back to AppConfig.data_files for interactive sessions.
    """
    context = CONTEXT.get()
    suite_scenario = context.get("suite_scenario") if context else None

    if suite_scenario:
        yield suite_scenario
    else:
        yield get_settings().data_files


@dependency(AppConfig)
def app_config() -> Generator[AppConfig, None, None]:
    """Provides the application configuration for dependency injection.

    Returns:
        An instance of AppConfig.
    """
    yield cast(AppConfig, get_settings())


@dependency(FlightBlenderClient)
async def flight_blender_client(config: AppConfig, data_files: DataFiles) -> AsyncGenerator[FlightBlenderClient, None]:
    """Provides a FlightBlenderClient instance for dependency injection.

    Args:
        config: The application configuration containing Flight Blender settings.
        data_files: The data files configuration.
    Returns:
        An instance of FlightBlenderClient.
    """
    auth_provider = get_auth_provider(config.flight_blender.auth)
    credentials = auth_provider.get_cached_credentials(
        audience=config.flight_blender.auth.audience,
        scopes=config.flight_blender.auth.scopes,
    )
    async with FlightBlenderClient(
        base_url=config.flight_blender.url,
        credentials=credentials,
        flight_declaration_path=data_files.flight_declaration,
        flight_declaration_via_operational_intent=data_files.flight_declaration_via_operational_intent,
        trajectory_path=data_files.trajectory,
        geo_fence_path=data_files.geo_fence,
    ) as fb_client:
        yield fb_client


@dependency(OpenSkyClient)
async def opensky_client(config: AppConfig) -> AsyncGenerator[OpenSkyClient, None]:
    """Provides an OpenSkyClient instance for dependency injection."""
    settings = OpenSkySettings.from_config(config.opensky)
    async with OpenSkyClient(settings) as client:
        yield client


@dependency(AirTrafficClient)
async def air_traffic_client(config: AppConfig, data_files: DataFiles) -> AsyncGenerator[AirTrafficClient, None]:
    """Provides an AirTrafficClient instance for dependency injection."""
    settings = AirTrafficSettings.from_config(
        config.air_traffic_simulator_settings,
        trajectory_path=data_files.trajectory,
    )
    async with AirTrafficClient(settings) as client:
        yield client


@dependency(SessionManager)
async def session_manager() -> AsyncGenerator[SessionManager, None]:
    yield SessionManager()


@dependency(CommonClient)
async def common_client() -> AsyncGenerator[CommonClient, None]:
    yield CommonClient()


@dependency(BlueSkyClient)
async def bluesky_client(config: AppConfig, data_files: DataFiles) -> AsyncGenerator[BlueSkyClient, None]:
    """Provides a BlueSkyClient instance for dependency injection."""
    settings = BlueSkyAirTrafficSettings.from_config(
        config.blue_sky_air_traffic_simulator_settings,
        simulation_path=data_files.simulation,
    )
    async with BlueSkyClient(settings) as client:
        yield client


@dependency(BayesianTrafficClient)
async def bayesian_air_traffic_client(config: AppConfig, data_files: DataFiles) -> AsyncGenerator[BayesianTrafficClient, None]:
    """Provides a BayesianTrafficClient instance for dependency injection."""
    settings = BayesianAirTrafficSettings.from_config(
        config.bayesian_air_traffic_simulator_settings,
        simulation_path=data_files.simulation,
    )
    async with BayesianTrafficClient(settings) as client:
        yield client


@dependency(AMQPClient)
async def amqp_client(config: AppConfig) -> AsyncGenerator[AMQPClient, None]:
    """Provides an AMQPClient instance for dependency injection."""
    settings = AMQPSettings.from_config(config.amqp) if config.amqp else AMQPSettings()
    async with AMQPClient(settings) as client:
        yield client


@dependency(AirTrafficStepClient)
async def air_traffic_step_client() -> AsyncGenerator[AirTrafficStepClient, None]:
    """Provides an AirTrafficStepClient instance for the unified Stream Air Traffic step."""
    async with AirTrafficStepClient() as client:
        yield client
