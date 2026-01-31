"""Unified air traffic streaming step.

This module provides a single scenario step for all air traffic operations,
replacing the multiple provider-specific steps with a unified interface.
"""

from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.core.providers import ProviderType, create_provider
from openutm_verification.core.streamers import StreamResult, TargetType, create_streamer


class AirTrafficStepClient:
    """Client providing the unified Stream Air Traffic step.

    This client wraps the provider/streamer architecture to expose a single
    scenario step that can handle all air traffic generation and streaming
    operations.
    """

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    @scenario_step("Stream Air Traffic")
    async def stream_air_traffic(
        self,
        provider: ProviderType,
        duration: int,
        target: TargetType = "flight_blender",
        *,
        # Provider settings (optional overrides)
        config_path: str | None = None,
        number_of_aircraft: int | None = None,
        sensor_ids: list[str] | None = None,
        session_ids: list[str] | None = None,
        viewport: tuple[float, float, float, float] | None = None,
    ) -> StreamResult:
        """Stream air traffic data from a provider to a target system.

        Unified step for all air traffic generation and streaming operations.
        Supports synthetic data generation (GeoJSON, BlueSky, Bayesian) and
        live data fetching (OpenSky Network).

        Args:
            provider: Data source - geojson, bluesky, bayesian, or opensky.
            duration: Streaming duration in seconds.
            target: Delivery target - flight_blender, amqp, or none (default: flight_blender).
            config_path: Path to configuration file (provider-specific).
            number_of_aircraft: Number of aircraft to simulate.
            sensor_ids: Sensor UUIDs for observations.
            session_ids: Session UUIDs for grouping.
            viewport: Geographic bounds for OpenSky (lat_min, lat_max, lon_min, lon_max).

        Returns:
            StreamResult with success status, counts, and optionally the observations.

        Example YAML:
            - step: Stream Air Traffic
              arguments:
                provider: geojson
                duration: 30
                target: flight_blender
                config_path: config/bern/trajectory.geojson
        """
        # Build provider from arguments
        provider_instance = create_provider(
            name=provider,
            config_path=config_path,
            number_of_aircraft=number_of_aircraft,
            duration=duration,
            sensor_ids=sensor_ids,
            session_ids=session_ids,
            viewport=viewport,
        )

        # Build streamer (or null streamer for target=none)
        streamer_instance = create_streamer(
            name=target,
            session_ids=session_ids,
        )

        # Execute streaming
        return await streamer_instance.stream_from_provider(
            provider=provider_instance,
            duration_seconds=duration,
        )
