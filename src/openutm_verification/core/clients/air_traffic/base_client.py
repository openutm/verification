from pydantic_settings import BaseSettings

from openutm_verification.core.execution.config_models import get_settings

config = get_settings()


class AirTrafficError(Exception):
    """Custom exception for Air Traffic API errors."""


class AirTrafficSettings(BaseSettings):
    """Pydantic settings for Air Traffic API with automatic .env loading."""

    # Simulation settings
    simulation_config_path: str
    simulation_duration_seconds: int = 30
    number_of_aircraft: int = 2
    single_or_multiple_sensors: str = "single"
    sensor_ids: list[str] = []


class BlueSkyAirTrafficSettings(BaseSettings):
    """Pydantic settings for BlueSky Air Traffic API with automatic .env loading."""

    # Simulation settings
    simulation_config_path: str
    simulation_duration_seconds: int = 30
    number_of_aircraft: int = 2
    single_or_multiple_sensors: str = "single"
    sensor_ids: list[str] = []


def create_air_traffic_settings() -> AirTrafficSettings:
    """Factory function to create AirTrafficSettings from config after initialization."""
    return AirTrafficSettings(
        simulation_config_path=config.data_files.trajectory or "",
        simulation_duration_seconds=config.air_traffic_simulator_settings.simulation_duration_seconds or 30,
        number_of_aircraft=config.air_traffic_simulator_settings.number_of_aircraft or 2,
        single_or_multiple_sensors=config.air_traffic_simulator_settings.single_or_multiple_sensors or "single",
        sensor_ids=config.air_traffic_simulator_settings.sensor_ids or [],
    )


def create_blue_sky_air_traffic_settings() -> BlueSkyAirTrafficSettings:
    """Factory function to create BlueSkyAirTrafficSettings from config after initialization."""
    return BlueSkyAirTrafficSettings(
        simulation_config_path=config.data_files.trajectory or "",
        simulation_duration_seconds=config.blue_sky_air_traffic_simulator_settings.simulation_duration_seconds or 30,
        number_of_aircraft=config.blue_sky_air_traffic_simulator_settings.number_of_aircraft or 2,
        single_or_multiple_sensors=config.blue_sky_air_traffic_simulator_settings.single_or_multiple_sensors or "single",
        sensor_ids=config.blue_sky_air_traffic_simulator_settings.sensor_ids or [],
    )


class BaseAirTrafficAPIClient:
    """Base client for Air Traffic API interactions with OAuth2 authentication."""

    def __init__(self, settings: AirTrafficSettings):
        self.settings = settings

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class BaseBlueSkyAirTrafficClient:
    """Base client for BlueSky Air Traffic API interactions with OAuth2 authentication."""

    def __init__(self, settings: BlueSkyAirTrafficSettings):
        self.settings = settings

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
