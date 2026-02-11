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
    def from_kwargs(
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
            except ValueError:
                logger.warning("Invalid session ID format detected, will auto-generate. Ensure session IDs are valid UUIDs.")
        return cls(session_ids=parsed_ids)

    def _make_result(
        self,
        *,
        success: bool,
        provider_name: str,
        duration_seconds: int,
        total_observations: int = 0,
        total_batches: int = 0,
        errors: list[str] | None = None,
        observations: list | None = None,
    ) -> StreamResult:
        """Helper to construct StreamResult with common fields."""
        return StreamResult(
            success=success,
            provider=provider_name,
            target=self.name,
            duration_seconds=duration_seconds,
            total_observations=total_observations,
            total_batches=total_batches,
            errors=errors or [],
            observations=observations or [],
        )

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
            return self._make_result(
                success=True,
                provider_name=provider.name,
                duration_seconds=duration_seconds,
            )

        # Get and validate Flight Blender configuration
        config = get_settings()

        if not config.flight_blender.url:
            error_msg = "Flight Blender URL is not configured. Please set 'flight_blender.url' in your configuration."
            logger.error(error_msg)
            return self._make_result(
                success=False,
                provider_name=provider.name,
                duration_seconds=duration_seconds,
                errors=[error_msg],
                observations=observations,
            )

        username = config.flight_blender.auth.username
        password = config.flight_blender.auth.password

        if not username or not password:
            error_msg = (
                "Flight Blender credentials are not configured. "
                "Please set 'flight_blender.auth.username' and "
                "'flight_blender.auth.password' in your configuration."
            )
            logger.error(error_msg)
            return self._make_result(
                success=False,
                provider_name=provider.name,
                duration_seconds=duration_seconds,
                errors=[error_msg],
                observations=observations,
            )

        try:
            async with FlightBlenderClient(
                base_url=config.flight_blender.url,
                credentials={"username": username, "password": password},
            ) as client:
                result = await client.submit_simulated_air_traffic(
                    observations=observations,
                    session_ids=self._session_ids,
                )

                return self._make_result(
                    success=result.get("success", False),
                    provider_name=provider.name,
                    duration_seconds=duration_seconds,
                    total_observations=sum(len(batch) for batch in observations),
                    total_batches=len(observations),
                    observations=observations,
                )

        except Exception as e:
            logger.error(f"Flight Blender streaming failed: {e}")
            return self._make_result(
                success=False,
                provider_name=provider.name,
                duration_seconds=duration_seconds,
                errors=[str(e)],
                observations=observations,
            )
