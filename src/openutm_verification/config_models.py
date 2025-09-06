"""
Pydantic models for application configuration.
"""

from enum import StrEnum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Status(StrEnum):
    """Enumeration for status values."""

    PASS = "PASS"
    FAIL = "FAIL"


class AuthConfig(BaseModel):
    """Authentication configuration for Flight Blender."""

    type: Literal["none", "passport"] = "none"
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    audience: str
    scopes: List[str]


class FlightBlenderConfig(BaseModel):
    """Flight Blender connection details."""

    url: str
    auth: AuthConfig = Field(default_factory=AuthConfig)


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
    run_id: Optional[str] = None
    flight_blender: FlightBlenderConfig
    scenarios: List[str] = Field(default_factory=list)
    reporting: ReportingConfig


# --- Reporting Models ---


class StepResult(BaseModel):
    """Data model for a single step within a scenario."""

    name: str
    status: Status
    duration: float
    details: Optional[Any] = None
    error_message: Optional[str] = None


class ScenarioResult(BaseModel):
    """Data model for the result of a single scenario."""

    name: str
    status: Status
    duration_seconds: float
    steps: List[StepResult]
    error_message: Optional[str] = None


class ReportSummary(BaseModel):
    """Summary of the entire verification run."""

    total_scenarios: int
    passed: int
    failed: int


class ReportData(BaseModel):
    """Root model for the final report data."""

    run_id: str
    tool_version: str
    start_time_utc: str
    end_time_utc: str
    total_duration_seconds: float
    overall_status: Status
    flight_blender_url: str
    deployment_details: DeploymentDetails
    config_file: str
    config: Dict[str, Any]
    results: List[ScenarioResult]
    summary: ReportSummary
