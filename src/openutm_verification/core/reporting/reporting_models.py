"""
Pydantic models for reporting configuration.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from uas_standards.astm.f3411.v22a.api import RIDAircraftState

from openutm_verification.core.execution.config_models import DeploymentDetails
from openutm_verification.simulator.models.declaration_models import (
    FlightDeclaration,
    FlightDeclarationViaOperationalIntent,
)
from openutm_verification.simulator.models.flight_data_types import (
    FlightObservationSchema,
)


class Status(StrEnum):
    """Enumeration for status values."""

    PASS = "success"
    FAIL = "failure"
    RUNNING = "running"
    SKIP = "skipped"


T = TypeVar("T")


class StepResult(BaseModel, Generic[T]):
    """Data model for a single step within a scenario."""

    id: str | None = None
    name: str
    status: Status
    duration: float
    result: T = None  # type: ignore
    error_message: str | None = None
    logs: list[str] = []


class ScenarioResult(BaseModel):
    """Data model for the result of a single scenario."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    suite_name: str | None = None
    status: Status
    duration: float
    steps: list[StepResult[Any]]
    error_message: str | None = None
    flight_declaration_filename: str | None = None
    telemetry_filename: str | None = None
    flight_declaration_data: FlightDeclaration | None = None
    flight_declaration_via_operational_intent_data: FlightDeclarationViaOperationalIntent | None = None
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
    start_time: datetime
    end_time: datetime
    total_duration: float
    overall_status: Status
    flight_blender_url: str
    deployment_details: DeploymentDetails
    config_file: str
    config: dict[str, Any]
    results: list[ScenarioResult]
    summary: ReportSummary
    docs_dir: str | None = None
