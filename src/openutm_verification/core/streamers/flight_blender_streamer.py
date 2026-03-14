"""Flight Blender streamer - sends observations to Flight Blender API.

Wraps the existing FlightBlenderClient's submit methods to provide
a consistent streaming interface.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from loguru import logger

from openutm_verification.auth.providers import get_auth_provider
from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.execution.config_models import get_settings
from openutm_verification.core.reporting.reporting_models import Status, StepResult

from .protocol import StreamResult

if TYPE_CHECKING:
    from openutm_verification.core.providers.protocol import AirTrafficProvider


class RefreshModeType(StrEnum):
    """Submission mode for Flight Blender streaming.

    Controls how observations are submitted to the Flight Blender API.
    StrEnum allows direct comparison with string values.
    """

    NORMAL = "normal"
    VARYING = "varying"


class FlightBlenderStreamer:
    """Streamer that sends observations to Flight Blender via HTTP API.

    Wraps the existing FlightBlenderClient's submit methods to provide
    the unified streaming interface. Supports both normal and varying
    refresh rate submission modes.
    """

    def __init__(
        self,
        session_ids: list[uuid.UUID] | None = None,
        refresh_mode: RefreshModeType = "normal",
    ):
        """Initialize the Flight Blender streamer.

        Args:
            session_ids: Optional list of session UUIDs for grouping observations.
            refresh_mode: Submission mode - "normal" for standard real-time playback,
                "varying" for corrupted timestamps simulating malfunctioning sensors.
        """
        self._session_ids = session_ids
        self._refresh_mode = refresh_mode

    @property
    def name(self) -> str:
        """Target identifier."""
        return "flight_blender"

    @classmethod
    def from_kwargs(
        cls,
        session_ids: list[str] | None = None,
        refresh_mode: RefreshModeType = "normal",
        **_kwargs,
    ) -> "FlightBlenderStreamer":
        """Factory method to create streamer from configuration.

        Args:
            session_ids: Optional list of session UUID strings.
            refresh_mode: Submission mode - "normal" or "varying".
        """
        parsed_ids = None
        if session_ids:
            try:
                parsed_ids = [uuid.UUID(sid) for sid in session_ids]
            except ValueError:
                logger.warning("Invalid session ID format detected, will auto-generate. Ensure session IDs are valid UUIDs.")
        return cls(session_ids=parsed_ids, refresh_mode=refresh_mode)

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
            observations=observations if observations is not None else None,
        )

    async def stream_from_provider(
        self,
        provider: "AirTrafficProvider",
        duration_seconds: int,
    ) -> StreamResult:
        """Stream observations from provider to Flight Blender.

        Gets observations from the provider, then submits them to Flight Blender.
        In "normal" mode, submits using standard real-time playback.
        In "varying" mode, uses the client's varying-refresh submission method
        which applies its own timestamp anomalies to simulate malfunctioning sensors.

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

        auth_provider = get_auth_provider(config.flight_blender.auth)
        credentials = auth_provider.get_cached_credentials(
            audience=config.flight_blender.auth.audience,
            scopes=config.flight_blender.auth.scopes,
        )

        try:
            async with FlightBlenderClient(
                base_url=config.flight_blender.url,
                credentials=credentials,
            ) as client:
                # Choose submission method based on refresh mode.
                # The varying-refresh client method applies its own timestamp
                # anomalies, so we always pass the original observations.
                if self._refresh_mode == "varying":
                    submit_fn = client.submit_simulated_air_traffic_at_random_refresh_rates
                else:
                    submit_fn = client.submit_simulated_air_traffic

                step_result = await submit_fn(
                    observations=observations,
                    session_ids=self._session_ids,
                )

                # The @scenario_step decorator wraps the return in StepResult.
                # Extract success from the inner result.
                if isinstance(step_result, StepResult):
                    if step_result.status == Status.FAIL:
                        raise RuntimeError(step_result.error_message or "Submission failed")
                    raw = step_result.result
                    success = raw.get("success", False) if isinstance(raw, dict) else True
                elif isinstance(step_result, dict):
                    success = step_result.get("success", False)
                else:
                    success = True

                return self._make_result(
                    success=success,
                    provider_name=provider.name,
                    duration_seconds=duration_seconds,
                    total_observations=len(observations),
                    total_batches=1,
                    observations=observations,
                )

        except Exception as e:
            logger.exception(f"Flight Blender streaming failed: {e}")
            return self._make_result(
                success=False,
                provider_name=provider.name,
                duration_seconds=duration_seconds,
                errors=[str(e)],
                observations=observations,
            )
