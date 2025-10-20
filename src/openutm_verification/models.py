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