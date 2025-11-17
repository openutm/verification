"""
Pydantic models for application configuration.
"""

from pathlib import Path
from typing import Annotated, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthConfig(StrictBaseModel):
    """Authentication configuration for Flight Blender."""

    type: Literal["none", "passport", "oauth2"] = "none"
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    audience: Optional[str] = None
    scopes: List[str] | None = None


class FlightBlenderConfig(StrictBaseModel):
    """Flight Blender connection details."""

    url: str
    auth: AuthConfig


class AirTrafficSimulatorSettings(StrictBaseModel):
    number_of_aircraft: int
    simulation_duration_seconds: int
    single_or_multiple_sensors: Literal["single", "multiple"] = "single"
    sensor_ids: List[str] = Field(default_factory=list)


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
    formats: List[str] = Field(default_factory=lambda: ["json", "html", "log"])
    deployment_details: DeploymentDetails = Field(default_factory=DeploymentDetails)


class DataFiles(StrictBaseModel):
    """Paths to data files used in the application."""

    telemetry: Optional[str] = None
    flight_declaration: Optional[str] = None
    geo_fence: Optional[str] = None

    @field_validator("telemetry", "flight_declaration", "geo_fence")
    @classmethod
    def validate_path(cls, v: Optional[str]) -> Optional[str]:
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

        if self.telemetry:
            self.telemetry = resolve_and_validate_path(self.telemetry, "Telemetry")
        if self.flight_declaration:
            self.flight_declaration = resolve_and_validate_path(self.flight_declaration, "Flight declaration")
        if self.geo_fence:
            self.geo_fence = resolve_and_validate_path(self.geo_fence, "Geo-fence")


class AppConfig(StrictBaseModel):
    """Root model for the application configuration."""

    version: str = "1.0"
    run_id: str = "daily-conformance-check"
    flight_blender: FlightBlenderConfig
    opensky: OpenSkyConfig
    air_traffic_simulator_settings: AirTrafficSimulatorSettings
    data_files: DataFiles
    scenarios: Dict[str, DataFiles | None] = Field(default_factory=dict)
    reporting: ReportingConfig

    def resolve_paths(self, config_file_path: Path) -> None:
        """Resolve all relative paths in the configuration to absolute paths."""
        base_path = config_file_path.parent
        self.data_files.resolve_paths(base_path)
        for scenario_data in self.scenarios.values():
            if scenario_data:
                scenario_data.resolve_paths(base_path)


ScenarioId = Annotated[str, "The unique identifier for a scenario"]


class RunContext(TypedDict):
    scenario_id: str


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
