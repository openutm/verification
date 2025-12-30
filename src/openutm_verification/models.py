from dataclasses import dataclass
from enum import Enum


class FlightBlenderError(Exception):
    """Custom exception for Flight Blender API errors."""


class CaseInsensitiveEnum(Enum):
    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.name.lower() == value.lower():
                    return member
        return super()._missing_(value)


class OperationState(int, CaseInsensitiveEnum):
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


class SDSPSessionAction(str, CaseInsensitiveEnum):
    START = "start"
    STOP = "stop"


class SpeedAccuracy(str, Enum):
    SAUnknown = "SAUnknown"
    SA10mpsPlus = "SA10mpsPlus"
    SA10mps = "SA10mps"
    SA3mps = "SA3mps"
    SA1mps = "SA1mps"
    SA03mps = "SA03mps"


@dataclass
class AircraftPosition:
    lat: float
    lng: float
    alt: float
    accuracy_h: str
    accuracy_v: str
    extrapolated: bool | None
    pressure_altitude: float | None


@dataclass
class AircraftState:
    position: AircraftPosition
    speed_accuracy: SpeedAccuracy
    speed: float | None = 255
    track: float | None = 361
    vertical_speed: float | None = 63


@dataclass
class TrackMessage:
    sdsdp_identifier: str
    unique_aircraft_identifier: str
    state: AircraftState
    timestamp: str
    source: str
    track_state: str


@dataclass
class SDSPTrackMessage:
    message: TrackMessage
    timestamp: str


@dataclass
class HeartbeatMessage:
    surveillance_sdsp_name: str
    meets_sla_surveillance_requirements: bool
    meets_sla_rr_lr_requirements: bool
    average_latency_or_95_percentile_latency_ms: int
    horizontal_or_vertical_95_percentile_accuracy_m: int
    timestamp: str


@dataclass
class SDSPHeartbeatMessage:
    message: HeartbeatMessage
    timestamp: str
