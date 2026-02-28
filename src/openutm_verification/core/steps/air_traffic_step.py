"""Unified air traffic streaming step.

This module provides a single scenario step for all air traffic operations,
replacing the multiple provider-specific steps with a unified interface.
"""

from __future__ import annotations

from loguru import logger

from openutm_verification.core.execution.config_models import get_settings
from openutm_verification.core.execution.dependency_resolution import CONTEXT
from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.core.providers import DataQualityType, ProviderType, create_provider
from openutm_verification.core.streamers import RefreshModeType, StreamResult, TargetType, create_streamer


def _get_data_file_path(field_name: str) -> str | None:
    """Get a data file path from the current suite context or global config.

    Checks the current CONTEXT for suite-specific overrides first,
    then falls back to the global config data_files.

    Args:
        field_name: Data file field name (e.g., "trajectory", "simulation").

    Returns:
        The resolved file path, or None if not configured.
    """
    try:
        context = CONTEXT.get()
        suite_scenario = context.get("suite_scenario") if context else None
        if suite_scenario and hasattr(suite_scenario, field_name):
            value = getattr(suite_scenario, field_name, None)
            if value:
                return value
    except (LookupError, AttributeError):
        pass

    try:
        config = get_settings()
        return getattr(config.data_files, field_name, None)
    except Exception:
        return None


class AirTrafficStepClient:
    """Client providing the unified Stream Air Traffic step.

    This client wraps the provider/streamer architecture to expose a single
    scenario step that can handle all air traffic generation and streaming
    operations. When step arguments are not provided, defaults are read
    from the application configuration.
    """

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def _apply_config_defaults(
        self,
        provider: ProviderType,
        *,
        duration: int | None,
        config_path: str | None,
        number_of_aircraft: int | None,
        sensor_ids: list[str] | None,
        session_ids: list[str] | None,
    ) -> tuple[int, str | None, int | None, list[str] | None, list[str] | None]:
        """Fill in missing parameters from application configuration.

        Reads defaults from the provider-specific config section when
        step arguments are not explicitly provided.

        Args:
            provider: The provider type to read defaults for.
            duration: Explicit duration or None.
            config_path: Explicit config path or None.
            number_of_aircraft: Explicit count or None.
            sensor_ids: Explicit sensor IDs or None.
            session_ids: Explicit session IDs or None.

        Returns:
            Tuple of (duration, config_path, number_of_aircraft, sensor_ids, session_ids)
            with defaults filled in.
        """
        try:
            app_config = get_settings()
        except Exception:
            logger.debug("Could not read application config for defaults, using step arguments only.")
            return (duration or 30, config_path, number_of_aircraft, sensor_ids, session_ids)

        try:
            if provider == "geojson":
                sim = app_config.air_traffic_simulator_settings
                if duration is None:
                    duration = sim.simulation_duration if hasattr(sim, "simulation_duration") else 30
                if number_of_aircraft is None:
                    number_of_aircraft = sim.number_of_aircraft
                if sensor_ids is None and sim.sensor_ids:
                    sensor_ids = sim.sensor_ids
                if session_ids is None and sim.session_ids:
                    session_ids = sim.session_ids
                if config_path is None:
                    config_path = _get_data_file_path("trajectory")

            elif provider == "bluesky":
                sim = app_config.blue_sky_air_traffic_simulator_settings
                if duration is None:
                    duration = sim.simulation_duration_seconds
                if number_of_aircraft is None:
                    number_of_aircraft = sim.number_of_aircraft
                if sensor_ids is None and sim.sensor_ids:
                    sensor_ids = sim.sensor_ids
                if session_ids is None and sim.session_ids:
                    session_ids = sim.session_ids
                if config_path is None:
                    config_path = _get_data_file_path("simulation")

            elif provider == "bayesian":
                sim = app_config.bayesian_air_traffic_simulator_settings
                if duration is None:
                    duration = sim.simulation_duration_seconds
                if number_of_aircraft is None:
                    number_of_aircraft = sim.number_of_aircraft
                if sensor_ids is None and sim.sensor_ids:
                    sensor_ids = sim.sensor_ids
                if session_ids is None and sim.session_ids:
                    session_ids = sim.session_ids

            elif provider == "opensky":
                pass  # OpenSky reads its own config in the provider
        except Exception:
            logger.debug("Could not read application config for defaults, using step arguments only.")

        # Ensure duration has a value
        if duration is None:
            duration = 30

        return (duration, config_path, number_of_aircraft, sensor_ids, session_ids)

    @scenario_step("Stream Air Traffic")
    async def stream_air_traffic(
        self,
        provider: ProviderType,
        duration: int | None = None,
        target: TargetType = "flight_blender",
        *,
        # Provider settings (optional overrides — defaults read from config)
        config_path: str | None = None,
        number_of_aircraft: int | None = None,
        sensor_ids: list[str] | None = None,
        session_ids: list[str] | None = None,
        viewport: tuple[float, float, float, float] | None = None,
        # Data quality mode
        data_quality: DataQualityType = "nominal",
        # Streamer settings
        refresh_mode: RefreshModeType = "normal",
    ) -> StreamResult:
        """Stream air traffic data from a provider to a target system.

        Unified step for all air traffic generation and streaming operations.
        Supports synthetic data generation (GeoJSON, BlueSky, Bayesian) and
        live data fetching (OpenSky Network).

        When arguments are not provided, defaults are read from the application
        configuration (e.g., air_traffic_simulator_settings, data_files).

        Args:
            provider: Data source - geojson, bluesky, bayesian, or opensky.
            duration: Streaming duration in seconds (defaults from config).
            target: Delivery target - flight_blender, amqp, or none (default: flight_blender).
            config_path: Path to configuration file (provider-specific, defaults from data_files).
            number_of_aircraft: Number of aircraft to simulate (defaults from config).
            sensor_ids: Sensor UUIDs for observations (defaults from config).
            session_ids: Session UUIDs for grouping (defaults from config).
            viewport: Geographic bounds for OpenSky (lat_min, lat_max, lon_min, lon_max).
            data_quality: Data quality mode - "nominal" or "latency" for simulated sensor issues.
            refresh_mode: Submission mode - "normal" or "varying" for corrupted timestamps.

        Returns:
            StreamResult with success status, counts, and optionally the observations.

        Example YAML:
            - step: Stream Air Traffic
              arguments:
                provider: geojson
                duration: 30
                target: flight_blender
                config_path: config/bern/trajectory.geojson

            # Minimal form (reads all defaults from config):
            - step: Stream Air Traffic
              arguments:
                provider: bayesian

            # With latency simulation:
            - step: Stream Air Traffic
              arguments:
                provider: bluesky
                data_quality: latency
        """
        # Apply config defaults for any unset parameters
        duration, config_path, number_of_aircraft, sensor_ids, session_ids = self._apply_config_defaults(
            provider,
            duration=duration,
            config_path=config_path,
            number_of_aircraft=number_of_aircraft,
            sensor_ids=sensor_ids,
            session_ids=session_ids,
        )

        # Build provider from arguments
        provider_instance = create_provider(
            name=provider,
            config_path=config_path,
            number_of_aircraft=number_of_aircraft,
            duration=duration,
            sensor_ids=sensor_ids,
            session_ids=session_ids,
            viewport=viewport,
            data_quality=data_quality,
        )

        # Build streamer (or null streamer for target=none)
        streamer_instance = create_streamer(
            name=target,
            session_ids=session_ids,
            refresh_mode=refresh_mode,
        )

        # Execute streaming
        stream_result = await streamer_instance.stream_from_provider(
            provider=provider_instance,
            duration_seconds=duration,
        )

        # If streaming failed, raise so the scenario step is marked as failed
        if not stream_result.success:
            raise RuntimeError(f"Air traffic streaming failed: {stream_result.errors}")

        return stream_result
