from dataclasses import dataclass
from enum import Enum


class FlightBlenderError(Exception):
    """Custom exception for Flight Blender API errors."""


class OperationState(int, Enum):
    """An enumeration for the state of a flight operation."""

    PROCESSING = 0
    ACCEPTED = 1
    ACTIVATED = 2
    NONCONFORMING = 3
    CONTINGENT = 4
    ENDED = 5
    WITHDRAWN = 6
    CANCELLED = 7
    REJECTED = 8


class SDSPSessionAction(str, Enum):
    START = "start"
    STOP = "stop"


@dataclass
class HeartbeatMessage:
    surveillance_sdsp_name: str
    meets_sla_surveillance_requirements: bool
    meets_sla_rr_lr_requirements: bool
    average_latenccy_or_95_percentile_latency_ms: int
    horizontal_or_vertical_95_percentile_accuracy_m: int
    timestamp: str


@dataclass
class SDSPHeartbeatMessage:
    message: HeartbeatMessage
    timestamp: str
