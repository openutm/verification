"""Flight Blender streamer - sends observations to Flight Blender API.

Wraps the existing FlightBlenderClient's submit methods to provide
a consistent streaming interface.
"""

from __future__ import annotations

import random
import uuid
from typing import TYPE_CHECKING, Literal

from loguru import logger

from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.execution.config_models import get_settings
from openutm_verification.core.reporting.reporting_models import Status, StepResult

from .protocol import StreamResult

if TYPE_CHECKING:
    from openutm_verification.core.providers.protocol import AirTrafficProvider

RefreshModeType = Literal["normal", "varying"]


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

    @staticmethod
    def _corrupt_timestamps(
        observations: list[list],
    ) -> list[list]:
        """Apply timestamp corruption to simulate malfunctioning sensors.

        Randomly applies anomalies to observation timestamps:
        - 30% chance: stale timestamp (repeat previous)
        - 20% chance: backward jump (10-60s into the past)
        - 15% chance: forward jump (10-60s into the future)
        - 35% chance: keep original (normal)

        Args:
            observations: List of observation lists per aircraft.

        Returns:
            New observation lists with corrupted timestamps.
        """
        corrupted_observations = []
        for aircraft_obs in observations:
            corrupted_aircraft_obs = []
            last_used_timestamp: int | None = None
            for obs in aircraft_obs:
                original_timestamp = obs.timestamp
                anomaly_roll = random.random()

                if anomaly_roll < 0.3 and last_used_timestamp is not None:
                    new_timestamp = last_used_timestamp
                    logger.debug(f"[off-nominal] Stale timestamp for {obs.icao_address}: kept {new_timestamp} instead of {original_timestamp}")
                elif anomaly_roll < 0.5:
                    offset = random.randint(10, 60)
                    new_timestamp = original_timestamp - offset
                    logger.debug(f"[off-nominal] Backward jump for {obs.icao_address}: {original_timestamp} -> {new_timestamp} (-{offset}s)")
                elif anomaly_roll < 0.65:
                    offset = random.randint(10, 60)
                    new_timestamp = original_timestamp + offset
                    logger.debug(f"[off-nominal] Forward jump for {obs.icao_address}: {original_timestamp} -> {new_timestamp} (+{offset}s)")
                else:
                    new_timestamp = original_timestamp

                corrupted_obs = obs.model_copy(update={"timestamp": new_timestamp})
                corrupted_aircraft_obs.append(corrupted_obs)
                last_used_timestamp = new_timestamp

            corrupted_observations.append(corrupted_aircraft_obs)
        return corrupted_observations

    async def stream_from_provider(
        self,
        provider: "AirTrafficProvider",
        duration_seconds: int,
    ) -> StreamResult:
        """Stream observations from provider to Flight Blender.

        Gets observations from the provider, then submits them to Flight Blender.
        In "normal" mode, submits using standard real-time playback.
        In "varying" mode, corrupts timestamps before submission to simulate
        malfunctioning sensors.

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

        # Apply timestamp corruption for varying refresh mode
        submit_observations = observations
        if self._refresh_mode == "varying":
            logger.info("Applying timestamp corruption for varying refresh rate submission")
            submit_observations = self._corrupt_timestamps(observations)

        try:
            async with FlightBlenderClient(
                base_url=config.flight_blender.url,
                credentials={"username": username, "password": password},
            ) as client:
                # Choose submission method based on refresh mode
                if self._refresh_mode == "varying":
                    submit_fn = client.submit_simulated_air_traffic_at_random_refresh_rates
                else:
                    submit_fn = client.submit_simulated_air_traffic

                step_result = await submit_fn(
                    observations=submit_observations,
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
                    total_observations=sum(len(batch) for batch in observations),
                    total_batches=len(observations),
                    observations=observations,
                )

        except Exception as e:
            logger.exception(f"Flight Blender streaming failed: {e}")
            raise
