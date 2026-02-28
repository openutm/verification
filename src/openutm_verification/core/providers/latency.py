"""Latency simulation utilities for air traffic providers.

Applies realistic sensor latency effects to observation data:
- Random observation drops (simulating missed readings)
- Timestamp shifts (simulating delayed sensor data)

These effects are consistent across all providers (GeoJSON, BlueSky, Bayesian)
and match the original per-client implementations.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Literal

from loguru import logger

if TYPE_CHECKING:
    from openutm_verification.core.providers.protocol import AirTrafficProvider
    from openutm_verification.simulator.models.flight_data_types import (
        FlightObservationSchema,
    )

# Default latency parameters — consistent with the original per-client implementations
LATENCY_PROBABILITY = 0.1  # 10% chance per observation
TIMESTAMP_SHIFT_RANGE_SECONDS = (-1, 2.5)  # Shift range in seconds

DataQualityType = Literal["nominal", "latency"]


def apply_latency(
    observations: list[list[FlightObservationSchema]],
    *,
    latency_probability: float = LATENCY_PROBABILITY,
    timestamp_shift_range: tuple[float, float] = TIMESTAMP_SHIFT_RANGE_SECONDS,
) -> list[list[FlightObservationSchema]]:
    """Apply simulated sensor latency effects to observations.

    For each observation, there is a configurable probability of being affected:
    - 50% chance: drop the observation entirely (simulating missed readings)
    - 50% chance: shift the timestamp (simulating delayed sensor data)

    Args:
        observations: List of observation lists per aircraft.
        latency_probability: Probability each observation is affected (0.0-1.0).
        timestamp_shift_range: Range (min, max) for timestamp shifts in seconds.

    Returns:
        Modified observation lists with latency effects applied.
    """
    modified_observations = []
    total_dropped = 0
    total_shifted = 0

    for track_observations in observations:
        modified_track = []
        for obs in track_observations:
            if random.random() < latency_probability:
                if random.random() < 0.5:
                    # Drop the observation entirely
                    total_dropped += 1
                    continue
                # Shift the timestamp (in seconds, matching the timestamp unit)
                shift_seconds = random.uniform(*timestamp_shift_range)
                new_timestamp = obs.timestamp + int(shift_seconds)
                obs = obs.model_copy(update={"timestamp": new_timestamp})
                total_shifted += 1
            modified_track.append(obs)
        modified_observations.append(modified_track)

    logger.info(f"Latency simulation applied: {total_dropped} observations dropped, {total_shifted} timestamps shifted")
    return modified_observations


class LatencyProviderWrapper:
    """Wraps an air traffic provider to add latency simulation to its observations.

    This decorator pattern preserves the original provider's name while applying
    latency post-processing to the generated observations.
    """

    def __init__(self, inner: AirTrafficProvider):
        self._inner = inner

    @property
    def name(self) -> str:
        """Provider identifier (passes through to inner provider)."""
        return self._inner.name

    async def get_observations(
        self,
        duration: int | None = None,
    ) -> list[list[FlightObservationSchema]]:
        """Get observations with latency effects applied.

        Args:
            duration: Override duration in seconds.

        Returns:
            Observation lists with simulated latency effects.
        """
        observations = await self._inner.get_observations(duration=duration)
        return apply_latency(observations)
