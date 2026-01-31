"""Protocol definitions and data models for air traffic streamers.

Streamers are responsible for delivering air traffic observations to target systems.
They abstract the delivery mechanism (HTTP, AMQP, etc.) behind a common interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from openutm_verification.core.providers.protocol import AirTrafficProvider
    from openutm_verification.simulator.models.flight_data_types import (
        FlightObservationSchema,
    )


@dataclass
class StreamResult:
    """Result of a streaming operation.

    Contains success status, statistics, and optionally the observation data
    for use by downstream steps.
    """

    success: bool
    provider: str
    target: str
    duration_seconds: int
    total_observations: int
    total_batches: int
    errors: list[str] = field(default_factory=list)

    # For downstream steps - stores the observations that were streamed
    observations: list[list["FlightObservationSchema"]] | None = None


@runtime_checkable
class AirTrafficStreamer(Protocol):
    """Protocol for delivering observations to a target system.

    Streamers take observations from a provider and deliver them to a specific
    target (Flight Blender, AMQP, or nowhere for testing).
    """

    @property
    def name(self) -> str:
        """Target identifier (e.g., 'flight_blender', 'amqp', 'none')."""
        ...

    async def stream_from_provider(
        self,
        provider: "AirTrafficProvider",
        duration_seconds: int,
    ) -> StreamResult:
        """Stream all data from a provider to this target.

        Args:
            provider: The air traffic provider to get observations from.
            duration_seconds: Duration for the streaming operation.

        Returns:
            StreamResult with statistics and optionally the observations.
        """
        ...
