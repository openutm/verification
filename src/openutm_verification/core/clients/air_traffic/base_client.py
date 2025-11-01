from typing import Optional, Tuple

import httpx
from loguru import logger
from pydantic_settings import BaseSettings

from openutm_verification.auth.oauth2 import OAuth2Client
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


def create_air_traffic_settings() -> AirTrafficSettings:
    """Factory function to create AirTrafficSettings from config after initialization."""
    return AirTrafficSettings(
        simulation_config_path=config.data_files.telemetry or "",
        simulation_duration_seconds=config.air_traffic_simulator_settings.simulation_duration_seconds or 30,
        number_of_aircraft=config.air_traffic_simulator_settings.number_of_aircraft or 2,
        single_or_multiple_sensors=config.air_traffic_simulator_settings.single_or_multiple_sensors or "single",
    )


class BaseAirTrafficAPIClient:
    """Base client for Air Traffic API interactions with OAuth2 authentication."""

    def __init__(self, settings: AirTrafficSettings):
        self.settings = settings

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
