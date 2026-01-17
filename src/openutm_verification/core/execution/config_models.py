"""
Pydantic models for application configuration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator

from openutm_verification.utils.time_utils import parse_duration


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthConfig(StrictBaseModel):
    """Authentication configuration for Flight Blender."""

    type: Literal["none", "passport", "oauth2"] = "none"
    client_id: str | None = None
    client_secret: str | None = None
    audience: str | None = None
    scopes: list[str] | None = None
    token_endpoint: str | None = None
    passport_base_url: str | None = None


class FlightBlenderConfig(StrictBaseModel):
    """Flight Blender connection details."""

    url: str
    auth: AuthConfig


class AirTrafficSimulatorSettings(StrictBaseModel):
    number_of_aircraft: int
    simulation_duration: int | str
    single_or_multiple_sensors: Literal["single", "multiple"] = "single"
    sensor_ids: list[str] = Field(default_factory=list)

    @field_validator("simulation_duration")
    @classmethod
    def validate_duration(cls, v: int | str) -> int:
        return int(parse_duration(v))


class BlueSkyAirTrafficSimulatorSettings(StrictBaseModel):
    number_of_aircraft: int
    simulation_duration_seconds: int
    single_or_multiple_sensors: Literal["single", "multiple"] = "single"
    sensor_ids: list[str] = Field(default_factory=list)


class OpenSkyConfig(StrictBaseModel):
    """OpenSky Network connection details."""

    auth: AuthConfig


class DeploymentDetails(StrictBaseModel):
    """Metadata about the deployment under test."""

    name: str = "Unknown"
    version: str = "Unknown"
    notes: str = ""


class ReportingConfig(StrictBaseModel):
    """Configuration for generating reports."""

    output_dir: str = "reports"
    formats: list[str] = Field(default_factory=lambda: ["json", "html", "log"])
    deployment_details: DeploymentDetails = Field(default_factory=DeploymentDetails)


class DataFiles(StrictBaseModel):
    """Paths to data files used in the application."""

    trajectory: str | None = None
    simulation: str | None = None
    flight_declaration: str | None = None
    geo_fence: str | None = None
    flight_declaration_via_operational_intent: str | None = None

    @field_validator(
        "trajectory",
        "simulation",
        "flight_declaration",
        "flight_declaration_via_operational_intent",
        "geo_fence",
    )
    @classmethod
    def validate_path(cls, v: str | None) -> str | None:
        """Validate that path is a non-empty string if provided."""
        if v is not None:
            if not isinstance(v, str):
                raise ValueError("Path must be a string")
            if not v.strip():
                raise ValueError("Path cannot be empty")
        return v

    def resolve_paths(self, base_path: Path) -> None:
        """Resolve relative paths to absolute paths based on the config file directory.

        Validates that files exist and raises clear error messages if they don't.
        """

        def resolve_and_validate_path(path_str: str, field_name: str) -> str:
            """Helper to resolve and validate a single path."""
            resolved = (base_path / path_str).resolve()
            if not resolved.exists():
                raise FileNotFoundError(f"{field_name} configuration file not found: {resolved}")
            if not resolved.is_file():
                raise ValueError(f"{field_name} path is not a file: {resolved}")
            return str(resolved)

        if self.trajectory:
            self.trajectory = resolve_and_validate_path(self.trajectory, "Trajectory")
        if self.simulation:
            self.simulation = resolve_and_validate_path(self.simulation, "Simulation")
        if self.flight_declaration:
            self.flight_declaration = resolve_and_validate_path(self.flight_declaration, "Flight declaration")
        if self.flight_declaration_via_operational_intent:
            self.flight_declaration_via_operational_intent = resolve_and_validate_path(
                self.flight_declaration_via_operational_intent,
                "Flight declaration via operational intent",
            )
        if self.geo_fence:
            self.geo_fence = resolve_and_validate_path(self.geo_fence, "Geo-fence")


class SuiteScenario(DataFiles):
    """A scenario within a suite, allowing overrides."""

    name: str


class SuiteConfig(StrictBaseModel):
    """Configuration for a test suite."""

    scenarios: list[SuiteScenario] | None = Field(default_factory=list)

    def resolve_paths(self, base_path: Path) -> None:
        if self.scenarios:
            for scenario in self.scenarios:
                scenario.resolve_paths(base_path)


class AppConfig(StrictBaseModel):
    """Root model for the application configuration."""

    version: str = "1.0"
    run_id: str = "daily-conformance-check"
    flight_blender: FlightBlenderConfig
    opensky: OpenSkyConfig
    air_traffic_simulator_settings: AirTrafficSimulatorSettings
    blue_sky_air_traffic_simulator_settings: BlueSkyAirTrafficSimulatorSettings
    data_files: DataFiles
    suites: dict[str, SuiteConfig] = Field(default_factory=dict)
    reporting: ReportingConfig

    # Runtime only
    target_suites: list[str] = Field(default_factory=list)

    def resolve_paths(self, config_file_path: Path) -> None:
        """Resolve all relative paths in the configuration to absolute paths."""
        base_path = config_file_path.parent
        self.data_files.resolve_paths(base_path)
        for suite in self.suites.values():
            suite.resolve_paths(base_path)


ScenarioId = Annotated[str, "The unique identifier for a scenario"]


class RunContext(TypedDict):
    scenario_id: str
    docs: str | None
    suite_scenario: SuiteScenario | None
    suite_name: str | None


class ConfigMeta(type):
    def __getattr__(cls, item):
        if cls._config is None:
            raise TypeError("Config not initialized")
        return getattr(cls._config, item)


class ConfigProxy(metaclass=ConfigMeta):
    _config = None

    @classmethod
    def initialize(cls, settings: AppConfig):
        if cls._config is not None:
            raise TypeError("Config already initialized")
        cls._config = settings

    @classmethod
    def override(cls, settings):
        cls._config = settings

    @classmethod
    def close(cls):
        cls._config = None


config: type[ConfigProxy] = ConfigProxy


def get_settings() -> "type[ConfigProxy]":
    return config
