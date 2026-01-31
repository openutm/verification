"""Null streamer - collects data without sending anywhere.

Useful for testing, data generation without delivery, or when the target
system is not available.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .protocol import StreamResult

if TYPE_CHECKING:
    from openutm_verification.core.providers.protocol import AirTrafficProvider


class NullStreamer:
    """Streamer that collects observations without sending them anywhere.

    Useful for:
    - Testing provider implementations
    - Generating data for later processing
    - Scenarios where you want to capture data without delivery
    """

    @property
    def name(self) -> str:
        """Target identifier."""
        return "none"

    @classmethod
    def from_config(cls, **_kwargs) -> "NullStreamer":
        """Factory method to create streamer from configuration."""
        return cls()

    async def stream_from_provider(
        self,
        provider: "AirTrafficProvider",
        duration_seconds: int,
    ) -> StreamResult:
        """Collect observations from provider without sending.

        Args:
            provider: The air traffic provider to get observations from.
            duration_seconds: Duration passed to the provider.

        Returns:
            StreamResult with collected observations.
        """
        observations = await provider.get_observations(duration=duration_seconds)

        total_observations = sum(len(batch) for batch in observations)

        return StreamResult(
            success=True,
            provider=provider.name,
            target=self.name,
            duration_seconds=duration_seconds,
            total_observations=total_observations,
            total_batches=len(observations),
            errors=[],
            observations=observations,
        )
