"""Flight Blender streamer - sends observations to Flight Blender API.

Wraps the existing FlightBlenderClient's submit methods to provide
a consistent streaming interface.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from loguru import logger

from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.execution.config_models import get_settings

from .protocol import StreamResult

if TYPE_CHECKING:
    from openutm_verification.core.providers.protocol import AirTrafficProvider


class FlightBlenderStreamer:
    """Streamer that sends observations to Flight Blender via HTTP API.

    Wraps the existing FlightBlenderClient's submit_simulated_air_traffic
    method to provide the unified streaming interface.
    """

    def __init__(self, session_ids: list[uuid.UUID] | None = None):
        """Initialize the Flight Blender streamer.

        Args:
            session_ids: Optional list of session UUIDs for grouping observations.
        """
        self._session_ids = session_ids

    @property
    def name(self) -> str:
        """Target identifier."""
        return "flight_blender"

    @classmethod
    def from_config(
        cls,
        session_ids: list[str] | None = None,
        **_kwargs,
    ) -> "FlightBlenderStreamer":
        """Factory method to create streamer from configuration.

        Args:
            session_ids: Optional list of session UUID strings.
        """
        parsed_ids = None
        if session_ids:
            try:
                parsed_ids = [uuid.UUID(sid) for sid in session_ids]
            except ValueError as e:
                logger.warning(f"Invalid session ID format, will auto-generate: {e}")
        return cls(session_ids=parsed_ids)

    async def stream_from_provider(
        self,
        provider: "AirTrafficProvider",
        duration_seconds: int,
    ) -> StreamResult:
        """Stream observations from provider to Flight Blender.

        Gets observations from the provider, then submits them to Flight Blender
        in real-time playback mode (one observation per second per aircraft).

        Args:
            provider: The air traffic provider to get observations from.
            duration_seconds: Duration for observation generation.

        Returns:
            StreamResult with submission statistics.
        """
        # Get observations from provider
        observations = await provider.get_observations(duration=duration_seconds)

        if not observations:
            return StreamResult(
                success=True,
                provider=provider.name,
                target=self.name,
                duration_seconds=duration_seconds,
                total_observations=0,
                total_batches=0,
                errors=[],
                observations=[],
            )

        # Get Flight Blender configuration
        config = get_settings()
        credentials = {"username": config.flight_blender.auth.username, "password": config.flight_blender.auth.password}

        errors: list[str] = []

        try:
            async with FlightBlenderClient(
                base_url=config.flight_blender.url,
                credentials=credentials,
            ) as client:
                # Use existing submit method which handles real-time playback
                result = await client.submit_simulated_air_traffic(
                    observations=observations,
                    session_ids=self._session_ids,
                )

                total_observations = sum(len(batch) for batch in observations)

                return StreamResult(
                    success=result.get("success", False),
                    provider=provider.name,
                    target=self.name,
                    duration_seconds=duration_seconds,
                    total_observations=total_observations,
                    total_batches=len(observations),
                    errors=errors,
                    observations=observations,
                )

        except Exception as e:
            logger.error(f"Flight Blender streaming failed: {e}")
            errors.append(str(e))
            return StreamResult(
                success=False,
                provider=provider.name,
                target=self.name,
                duration_seconds=duration_seconds,
                total_observations=0,
                total_batches=0,
                errors=errors,
                observations=observations,
            )
