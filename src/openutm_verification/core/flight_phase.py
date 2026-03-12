"""
Flight phase taxonomy for verification step annotations.

Based on the IATA/CAST Flight Phase Taxonomy.
See: https://skybrary.aero/articles/flight-phase-taxonomy

Phases are optional annotations on scenario steps that allow grouping
related steps in reports and the UI.
"""

from enum import StrEnum


class FlightPhase(StrEnum):
    """IATA flight phase categories for annotating verification steps."""

    STANDING = "STD"
    """Pre-flight standing / setup / configuration."""

    PUSHBACK = "PBT"
    """Pushback or towing phase."""

    TAXI_OUT = "TXO"
    """Taxi-out phase."""

    TAKEOFF = "TOF"
    """Takeoff phase."""

    INITIAL_CLIMB = "ICL"
    """Initial climb phase."""

    EN_ROUTE = "ENR"
    """En route / cruise phase."""

    MANEUVERING = "MAN"
    """Maneuvering / holding / aerial work."""

    APPROACH = "APR"
    """Approach phase."""

    LANDING = "LDG"
    """Landing phase."""

    TAXI_IN = "TXI"
    """Taxi-in phase."""

    POST_FLIGHT = "PST"
    """Post-flight / parking / teardown."""


# Human-readable labels for display
FLIGHT_PHASE_LABELS: dict[FlightPhase, str] = {
    FlightPhase.STANDING: "Standing",
    FlightPhase.PUSHBACK: "Pushback / Towing",
    FlightPhase.TAXI_OUT: "Taxi Out",
    FlightPhase.TAKEOFF: "Takeoff",
    FlightPhase.INITIAL_CLIMB: "Initial Climb",
    FlightPhase.EN_ROUTE: "En Route",
    FlightPhase.MANEUVERING: "Maneuvering",
    FlightPhase.APPROACH: "Approach",
    FlightPhase.LANDING: "Landing",
    FlightPhase.TAXI_IN: "Taxi In",
    FlightPhase.POST_FLIGHT: "Post-Flight",
}
