"""
Pydantic models for application configuration.
"""

from enum import StrEnum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AuthConfig(BaseModel):
    """Authentication configuration for Flight Blender."""

    type: Literal["none", "passport", "oauth2"] = "none"
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    audience: Optional[str] = None
    scopes: List[str] | None = None


class FlightBlenderConfig(BaseModel):
    """Flight Blender connection details."""

    url: str
    auth: AuthConfig


class OpenSkyConfig(BaseModel):
    """OpenSky Network connection details."""

    auth: AuthConfig


class DeploymentDetails(BaseModel):
    """Metadata about the deployment under test."""

    name: str = "Unknown"
    version: str = "Unknown"
    notes: str = ""


class ReportingConfig(BaseModel):
    """Configuration for generating reports."""

    output_dir: str = "reports"
    formats: List[str] = Field(default_factory=lambda: ["json", "html", "log"])
    deployment_details: DeploymentDetails = Field(default_factory=DeploymentDetails)


class AppConfig(BaseModel):
    """Root model for the application configuration."""

    version: str = "1.0"
    run_id: str = "daily-conformance-check"
    flight_blender: FlightBlenderConfig
    opensky: OpenSkyConfig
    scenarios: List[str] = Field(default_factory=list)
    reporting: ReportingConfig


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


def get_settings() -> AppConfig:
    return config
