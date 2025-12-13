"""
Pydantic models for reporting configuration.
"""

from enum import StrEnum
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel
from uas_standards.astm.f3411.v22a.api import RIDAircraftState

from openutm_verification.core.execution.config_models import DeploymentDetails
from openutm_verification.simulator.models.declaration_models import FlightDeclaration


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
    error_message: Optional[str] = None


class ScenarioResult(BaseModel, arbitrary_types_allowed=True):
    """Data model for the result of a single scenario."""

    name: str
    suite_name: Optional[str] = None
    status: Status
    duration_seconds: float
    steps: List[StepResult[Any]]
    error_message: Optional[str] = None
    flight_declaration_filename: Optional[str] = None
    telemetry_filename: Optional[str] = None
    flight_declaration_data: Optional[FlightDeclaration] = None
    telemetry_data: Optional[list[RIDAircraftState]] = None
    visualization_2d_path: Optional[str] = None
    visualization_3d_path: Optional[str] = None
    docs: Optional[str] = None


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
    docs_dir: Optional[str] = None
