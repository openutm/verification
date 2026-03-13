"""
Flight phase taxonomy for verification step annotations.

Phases are optional annotations on scenario steps that allow grouping
related steps in reports and the UI.
"""

from enum import StrEnum


class FlightPhase(StrEnum):
    """Flight phase categories for annotating verification steps."""

    FLIGHT_PLANNING = "FPL"
    """Flight planning phase."""

    PRE_FLIGHT = "PRF"
    """Pre-flight checks and setup."""

    ENGINE_START = "ESD"
    """Engine start / depart phase."""

    TAXI_OUT = "TXO"
    """Taxi-out phase."""

    TAKEOFF = "TOF"
    """Takeoff phase."""

    REJECTED_TAKEOFF = "RTO"
    """Rejected takeoff phase."""

    INITIAL_CLIMB = "ICL"
    """Initial climb phase."""

    EN_ROUTE_CLIMB = "ERC"
    """En route climb phase."""

    CRUISE = "CRZ"
    """Cruise phase."""

    DESCENT = "DES"
    """Descent phase."""

    APPROACH = "APR"
    """Approach phase."""

    GO_AROUND = "GAR"
    """Go-around phase."""

    LANDING = "LDG"
    """Landing phase."""

    TAXI_IN = "TXI"
    """Taxi-in phase."""

    ARRIVAL = "AES"
    """Arrival / engine shutdown phase."""

    POST_FLIGHT = "PST"
    """Post-flight phase."""

    FLIGHT_CLOSE = "FCL"
    """Flight close phase."""

    GROUND_SERVICES = "GND"
    """Ground services phase."""


# Human-readable labels for display
FLIGHT_PHASE_LABELS: dict[FlightPhase, str] = {
    FlightPhase.FLIGHT_PLANNING: "Flight Planning",
    FlightPhase.PRE_FLIGHT: "Pre-flight",
    FlightPhase.ENGINE_START: "Engine Start / Depart",
    FlightPhase.TAXI_OUT: "Taxi Out",
    FlightPhase.TAKEOFF: "Takeoff",
    FlightPhase.REJECTED_TAKEOFF: "Rejected Takeoff",
    FlightPhase.INITIAL_CLIMB: "Initial Climb",
    FlightPhase.EN_ROUTE_CLIMB: "En Route Climb",
    FlightPhase.CRUISE: "Cruise",
    FlightPhase.DESCENT: "Descent",
    FlightPhase.APPROACH: "Approach",
    FlightPhase.GO_AROUND: "Go-around",
    FlightPhase.LANDING: "Landing",
    FlightPhase.TAXI_IN: "Taxi In",
    FlightPhase.ARRIVAL: "Arrival / Engine Shutdown",
    FlightPhase.POST_FLIGHT: "Post-flight",
    FlightPhase.FLIGHT_CLOSE: "Flight Close",
    FlightPhase.GROUND_SERVICES: "Ground Services",
}
