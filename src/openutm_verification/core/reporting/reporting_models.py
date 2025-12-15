"""
Pydantic models for reporting configuration.
"""

from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from uas_standards.astm.f3411.v22a.api import RIDAircraftState

from openutm_verification.core.execution.config_models import DeploymentDetails
from openutm_verification.simulator.models.declaration_models import FlightDeclaration
from openutm_verification.simulator.models.flight_data_types import FlightObservationSchema


class Status(StrEnum):
    """Enumeration for status values."""

    PASS = "PASS"
    FAIL = "FAIL"


T = TypeVar("T")


class StepResult(BaseModel, Generic[T]):
    """Data model for a single step within a scenario."""

    name: str
    status: Status
    duration: float
    details: T = None  # type: ignore
    error_message: str | None = None


class ScenarioResult(BaseModel):
    """Data model for the result of a single scenario."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    suite_name: str | None = None
    status: Status
    duration_seconds: float
    steps: list[StepResult[Any]]
    error_message: str | None = None
    flight_declaration_filename: str | None = None
    telemetry_filename: str | None = None
    flight_declaration_data: FlightDeclaration | None = None
    telemetry_data: list[RIDAircraftState] | None = None
    air_traffic_data: list[list[FlightObservationSchema]] | None = None
    visualization_2d_path: str | None = None
    visualization_3d_path: str | None = None
    docs: str | None = None


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
    config: dict[str, Any]
    results: list[ScenarioResult]
    summary: ReportSummary
    docs_dir: str | None = None
