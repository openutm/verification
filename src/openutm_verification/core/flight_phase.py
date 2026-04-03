"""
Flight phase taxonomy for verification step annotations.

Phases are optional annotations on scenario steps that allow grouping
related steps in reports and the UI.
"""

from enum import StrEnum


class FlightPhase(StrEnum):
    """Flight phase categories for annotating verification steps."""

    FLIGHT_PLANNING = "FLIGHT PLANNING"
    """Flight planning phase."""

    PRE_FLIGHT = "PRE FLIGHT"
    """Pre-flight checks and setup."""

    ENGINE_START = "ENGINE START"
    """Engine start / depart phase."""

    TAXI_OUT = "TAXI OUT"
    """Taxi-out phase."""

    TAKEOFF = "TAKEOFF"
    """Takeoff phase."""

    REJECTED_TAKEOFF = "REJECTED TAKEOFF"
    """Rejected takeoff phase."""

    INITIAL_CLIMB = "INITIAL CLIMB"
    """Initial climb phase."""

    EN_ROUTE_CLIMB = "EN ROUTE CLIMB"
    """En route climb phase."""

    CRUISE = "CRUISE"
    """Cruise phase."""

    DESCENT = "DESCENT"
    """Descent phase."""

    APPROACH = "APPROACH"
    """Approach phase."""

    GO_AROUND = "GO AROUND"
    """Go-around phase."""

    LANDING = "LANDING"
    """Landing phase."""

    TAXI_IN = "TAXI IN"
    """Taxi-in phase."""

    ARRIVAL = "ARRIVAL"
    """Arrival / engine shutdown phase."""

    POST_FLIGHT = "POST FLIGHT"
    """Post-flight phase."""

    FLIGHT_CLOSE = "FLIGHT CLOSE"
    """Flight close phase."""

    GROUND_SERVICES = "GROUND SERVICES"
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
