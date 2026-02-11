"""AMQP streamer - sends observations to AMQP/RabbitMQ.

Wraps the existing AMQPClient to provide a consistent streaming interface.
This is a placeholder implementation for future expansion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from .protocol import StreamResult

if TYPE_CHECKING:
    from openutm_verification.core.providers.protocol import AirTrafficProvider


class AMQPStreamer:
    """Streamer that sends observations to AMQP/RabbitMQ.

    Note: This is currently a placeholder implementation.
    Full AMQP streaming would require additional configuration
    and message formatting logic.
    """

    @property
    def name(self) -> str:
        """Target identifier."""
        return "amqp"

    @classmethod
    def from_kwargs(cls, **_kwargs) -> "AMQPStreamer":
        """Factory method to create streamer from keyword arguments."""
        return cls()

    async def stream_from_provider(
        self,
        provider: "AirTrafficProvider",
        duration_seconds: int,
    ) -> StreamResult:
        """Stream observations from provider to AMQP.

        Currently a placeholder - collects observations but logs a warning
        that AMQP streaming is not fully implemented.

        Args:
            provider: The air traffic provider to get observations from.
            duration_seconds: Duration for observation generation.

        Returns:
            StreamResult with observations (not actually sent to AMQP yet).
        """
        logger.warning("AMQP streaming is not fully implemented. Observations will be collected but not sent to AMQP.")

        # Get observations from provider
        observations = await provider.get_observations(duration=duration_seconds)

        total_observations = sum(len(batch) for batch in observations)

        return StreamResult(
            success=True,
            provider=provider.name,
            target=self.name,
            duration_seconds=duration_seconds,
            total_observations=total_observations,
            total_batches=len(observations),
            errors=["AMQP streaming not fully implemented - data collected but not sent"],
            observations=observations,
        )
