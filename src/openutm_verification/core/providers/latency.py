"""Latency simulation utilities for air traffic providers.

Applies realistic sensor latency effects to observation data:
- Random observation drops (simulating missed readings)
- Timestamp shifts (simulating delayed sensor data)

These effects are consistent across all providers (GeoJSON, BlueSky, Bayesian)
and match the original per-client implementations.
"""

from __future__ import annotations

import random
from enum import StrEnum
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from openutm_verification.core.providers.protocol import AirTrafficProvider
    from openutm_verification.simulator.models.flight_data_types import (
        FlightObservationSchema,
    )

# Default latency parameters — consistent with the original per-client implementations
LATENCY_PROBABILITY = 0.1  # 10% chance per observation
TIMESTAMP_SHIFT_RANGE_SECONDS = (-1, 2.5)  # Shift range in seconds


class DataQualityType(StrEnum):
    """Data quality modes for air traffic observations.

    Each quality type applies independent degradation effects to observation data.
    StrEnum allows direct comparison with string values (e.g., ``quality == "latency"``).
    """

    NOMINAL = "nominal"
    LATENCY = "latency"


def drop_observations(
    observations: list[FlightObservationSchema],
    probability: float = LATENCY_PROBABILITY,
) -> tuple[list[FlightObservationSchema], int]:
    """Randomly drop observations to simulate missed sensor readings.

    Each observation has an independent probability of being removed.

    Args:
        observations: Flat list of observations across all aircraft.
        probability: Probability each observation is dropped (0.0-1.0).

    Returns:
        Tuple of (modified observation list, total observations dropped).
    """
    kept = []
    total_dropped = 0
    for obs in observations:
        if random.random() < probability:
            total_dropped += 1
        else:
            kept.append(obs)
    return kept, total_dropped


def shift_timestamps(
    observations: list[FlightObservationSchema],
    probability: float = LATENCY_PROBABILITY,
    shift_range: tuple[float, float] = TIMESTAMP_SHIFT_RANGE_SECONDS,
) -> tuple[list[FlightObservationSchema], int]:
    """Randomly shift observation timestamps to simulate delayed sensor data.

    Each observation has an independent probability of having its timestamp
    shifted by a random amount within the given range (in seconds).

    Args:
        observations: Flat list of observations across all aircraft.
        probability: Probability each observation is shifted (0.0-1.0).
        shift_range: Range (min, max) for timestamp shifts in seconds.

    Returns:
        Tuple of (modified observation list, total observations shifted).
    """
    new_observations = []
    total_shifted = 0
    for obs in observations:
        if random.random() < probability:
            shift_seconds = random.uniform(*shift_range)
            obs = obs.model_copy(update={"timestamp": obs.timestamp + int(shift_seconds)})
            total_shifted += 1
        new_observations.append(obs)
    return new_observations, total_shifted


def apply_latency(
    observations: list[FlightObservationSchema],
    *,
    latency_probability: float = LATENCY_PROBABILITY,
    timestamp_shift_range: tuple[float, float] = TIMESTAMP_SHIFT_RANGE_SECONDS,
) -> list[FlightObservationSchema]:
    """Apply simulated sensor latency effects to observations.

    Composes independent quality degradation effects:
    1. Random observation drops (simulating missed readings)
    2. Random timestamp shifts (simulating delayed sensor data)

    Each effect is applied independently, making it straightforward to add
    new quality degradation types in the future.

    Args:
        observations: Flat list of observations across all aircraft.
        latency_probability: Base probability for each effect (0.0-1.0).
            Split equally between drops and shifts to maintain overall 50/50 ratio.
        timestamp_shift_range: Range (min, max) for timestamp shifts in seconds.

    Returns:
        Modified observation list with latency effects applied.
    """
    drop_prob = latency_probability / 2
    shift_prob = latency_probability / 2

    result, total_dropped = drop_observations(observations, probability=drop_prob)
    result, total_shifted = shift_timestamps(result, probability=shift_prob, shift_range=timestamp_shift_range)

    logger.info(f"Latency simulation applied: {total_dropped} observations dropped, {total_shifted} timestamps shifted")
    return result


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
    ) -> list[FlightObservationSchema]:
        """Get observations with latency effects applied.

        Args:
            duration: Override duration in seconds.

        Returns:
            Observation list with simulated latency effects.
        """
        observations = await self._inner.get_observations(duration=duration)
        return apply_latency(observations)
