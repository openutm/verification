from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from openutm_verification.core.execution.config_models import (
        AirTrafficSimulatorSettings as AirTrafficSimConfig,
    )
    from openutm_verification.core.execution.config_models import (
        BlueSkyAirTrafficSimulatorSettings as BlueSkySimConfig,
    )


class AirTrafficError(Exception):
    """Custom exception for Air Traffic API errors."""


class AirTrafficSettings(BaseModel):
    """Settings for Air Traffic API."""

    simulation_config_path: str = ""
    simulation_duration: int = 30
    number_of_aircraft: int = 2
    single_or_multiple_sensors: str = "single"
    sensor_ids: list[str] = []
    session_ids: list[str] = []

    @classmethod
    def from_config(cls, sim_config: "AirTrafficSimConfig", trajectory_path: str | None = None) -> "AirTrafficSettings":
        """Create settings from config."""
        return cls(
            simulation_config_path=trajectory_path or "",
            simulation_duration=sim_config.simulation_duration,
            number_of_aircraft=sim_config.number_of_aircraft,
            single_or_multiple_sensors=sim_config.single_or_multiple_sensors,
            sensor_ids=sim_config.sensor_ids,
            session_ids=sim_config.session_ids,
        )


class BlueSkyAirTrafficSettings(BaseModel):
    """Settings for BlueSky Air Traffic API."""

    simulation_config_path: str = ""
    simulation_duration_seconds: int = 30
    number_of_aircraft: int = 2
    single_or_multiple_sensors: str = "single"
    sensor_ids: list[str] = []
    session_ids: list[str] = []

    @classmethod
    def from_config(cls, sim_config: "BlueSkySimConfig", simulation_path: str | None = None) -> "BlueSkyAirTrafficSettings":
        """Create settings from config."""
        return cls(
            simulation_config_path=simulation_path or "",
            simulation_duration_seconds=sim_config.simulation_duration_seconds,
            number_of_aircraft=sim_config.number_of_aircraft,
            single_or_multiple_sensors=sim_config.single_or_multiple_sensors,
            sensor_ids=sim_config.sensor_ids,
            session_ids=sim_config.session_ids,
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
