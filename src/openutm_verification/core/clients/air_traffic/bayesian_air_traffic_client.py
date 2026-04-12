from __future__ import annotations

import json
import math
import random
import uuid
from pathlib import Path
from uuid import UUID

import arrow
from cam_track_gen import TrackGenerationSession, TrackResultData, get_available_model_files
from loguru import logger

from openutm_verification.core.clients.air_traffic.base_client import (
    SENSOR_MODE_MULTIPLE,
    BayesianAirTrafficClient,
    BayesianAirTrafficSettings,
)
from openutm_verification.core.clients.flight_blender.base_client import (
    BaseBlenderAPIClient,
)
from openutm_verification.core.execution.scenario_runner import internal_step
from openutm_verification.core.flight_phase import FlightPhase
from openutm_verification.simulator.models.flight_data_types import FlightObservationSchema


def random_icao():
    n = random.randrange(1, 0xFFFFFF)  # excludes 0x000000 and 0xFFFFFF
    return f"{n:06X}"


FEET_TO_METERS = 0.3048
FEET_TO_MM = FEET_TO_METERS * 1000

# Approximate meters per degree at mid-latitudes
_METERS_PER_DEG_LAT = 111_320.0


def _meters_per_deg_lon(lat_deg: float) -> float:
    return 111_320.0 * math.cos(math.radians(lat_deg))


def _load_area_bounds(config_path: str) -> tuple[float, float, float, float] | None:
    """Load a GeoJSON FeatureCollection and extract its bounding box.

    Returns (min_lon, min_lat, max_lon, max_lat) or None if the file
    doesn't exist or isn't valid GeoJSON.
    """
    p = Path(config_path)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        coords = []
        for feat in data.get("features", []):
            geom = feat.get("geometry", {})
            for c in geom.get("coordinates", []):
                if isinstance(c, (list, tuple)) and len(c) >= 2:
                    coords.append(c)
        if not coords:
            return None
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        return (min(lons), min(lats), max(lons), max(lats))
    except Exception:
        return None


class BayesianTrafficClient(BayesianAirTrafficClient, BaseBlenderAPIClient):
    """Bayesian client that loads and runs a .scn file and samples aircraft states at 1 Hz."""

    def __init__(self, settings: BayesianAirTrafficSettings):
        BayesianAirTrafficClient.__init__(self, settings)
        # Initialize BaseBlenderAPIClient with dummy values since we don't use it for HTTP requests here
        # but we inherit from it. Ideally, we should refactor to composition over inheritance.
        BaseBlenderAPIClient.__init__(self, base_url="", credentials={})

    @internal_step("Fetch Session IDs for Bayesian Simulation", phase=FlightPhase.PRE_FLIGHT)
    async def get_configured_bayesian_session_ids(
        self,
    ) -> list[UUID]:
        """Generate a new session ID for simulated air traffic data submission.

        Args:
            config_path: Path to the GeoJSON configuration file. Defaults to settings value.
        Returns:
            A new session ID as a string.
        """

        session_ids = self.settings.session_ids
        logger.debug(f"Using session IDs: {session_ids} from settings for Bayesian simulation.")
        try:
            # create a list of UUIDs with at least one UUID if session_ids is empty
            session_ids = [UUID(x) for x in session_ids] if session_ids else [uuid.uuid4()]

        except ValueError as exc:
            logger.error(f"Invalid session ID in configuration, it should be a valid UUID: {exc}")
            raise
        return session_ids

    @internal_step("Generate Bayesian Simulation Air Traffic Data", phase=FlightPhase.PRE_FLIGHT)
    async def generate_bayesian_sim_air_traffic_data(
        self,
        config_path: str | None = None,
        duration: int | None = None,
    ) -> list[FlightObservationSchema]:
        """Run Bayesian scenario and sample aircraft state every second.

        When *config_path* points to a GeoJSON FeatureCollection the
        generated tracks are relocated into that bounding box with random
        origins and heading rotations so that intruders approach from all
        directions.

        Args:
            config_path: Optional GeoJSON file whose bounds define the target area.
            duration: Simulation duration in seconds.
        Returns:
            list[FlightObservationSchema]: flat list of observations across all aircraft,
            time-series sampled at 1 Hz.
        """

        duration_in_seconds = int(duration or self.settings.simulation_duration or 30)
        number_of_aircraft = self.settings.number_of_aircraft or 3
        sensor_ids = self.settings.sensor_ids
        use_multiple_sensors = self.settings.single_or_multiple_sensors == SENSOR_MODE_MULTIPLE

        try:
            sensor_ids = [UUID(x) for x in sensor_ids] if sensor_ids else [uuid.uuid4()]
        except ValueError as exc:
            logger.error(f"Invalid sensor ID in configuration, it should be a valid UUID: {exc}")
            raise

        available_models = get_available_model_files()
        logger.info(f"Available models from cam-track-gen: {available_models}")

        if not available_models:
            logger.info("No models found.")
            return []

        model_filename = "Light_Aircraft_Below_10000_ft_Data.mat"
        logger.info(f"\nUsing model: {model_filename}")

        session = TrackGenerationSession.create_from_file(model_filename)
        if session is None:
            logger.info("Failed to create a session.")
            return []

        logger.info("Generating tracks...")
        tracks = session.generate_tracks(number_of_tracks=number_of_aircraft, simulation_duration_seconds=duration_in_seconds)

        if not tracks:
            logger.info("Track generation failed.")
            return []

        logger.info(f"Successfully generated {len(tracks)} tracks.")

        # Resolve target area from GeoJSON or fall back to EPSG 3347 identity
        area_bounds = _load_area_bounds(config_path) if config_path else None
        if area_bounds is not None:
            center_lon = (area_bounds[0] + area_bounds[2]) / 2
            center_lat = (area_bounds[1] + area_bounds[3]) / 2
            half_w_m = (area_bounds[2] - area_bounds[0]) * _meters_per_deg_lon(center_lat) / 2
            half_h_m = (area_bounds[3] - area_bounds[1]) * _METERS_PER_DEG_LAT / 2
            logger.info(f"Target area: center=({center_lat:.4f}, {center_lon:.4f}), size≈{2 * half_w_m:.0f}m × {2 * half_h_m:.0f}m")
        else:
            center_lon, center_lat = None, None
            half_w_m = half_h_m = 0.0

        now = arrow.utcnow()
        all_observations: list[FlightObservationSchema] = []

        for track_idx, track in enumerate(tracks):
            icao_address = random_icao()

            # Random heading rotation for direction diversity
            heading_offset_rad = random.uniform(0, 2 * math.pi)

            # Random origin offset within the target area
            if center_lon is not None and center_lat is not None:
                origin_lon = center_lon + random.uniform(-half_w_m, half_w_m) / _meters_per_deg_lon(center_lat)
                origin_lat = center_lat + random.uniform(-half_h_m, half_h_m) / _METERS_PER_DEG_LAT
            else:
                origin_lon, origin_lat = None, None

            observations = self._convert_track_to_observations(
                track=track,
                icao_address=icao_address,
                base_time=now,
                sensor_ids=sensor_ids,
                use_multiple_sensors=use_multiple_sensors,
                heading_offset_rad=heading_offset_rad,
                origin_lat=origin_lat,
                origin_lon=origin_lon,
            )
            all_observations.extend(observations)
            logger.info(f"Track {track_idx} ({icao_address}): {len(observations)} obs, heading_offset={math.degrees(heading_offset_rad):.0f}°")

        logger.info(f"Generated observations for {len(tracks)} tracks, with {len(all_observations)} total observations.")
        return all_observations

    @staticmethod
    def _convert_track_to_observations(
        track: TrackResultData,
        icao_address: str,
        base_time: arrow.Arrow,
        sensor_ids: list[UUID],
        use_multiple_sensors: bool,
        heading_offset_rad: float = 0.0,
        origin_lat: float | None = None,
        origin_lon: float | None = None,
    ) -> list[FlightObservationSchema]:
        """Convert a raw track from cam-track-gen to FlightObservationSchema list.

        The track contains positions in local Cartesian coordinates (feet)
        relative to (0, 0).  When *origin_lat/lon* are provided the track
        is placed at that WGS-84 origin and rotated by *heading_offset_rad*
        so that intruders approach from diverse directions.

        Timestamps use wall-clock microseconds (consistent with BlueSky).
        """
        times = track["time"]
        north_ft = track["north_position_feet"]
        east_ft = track["east_position_feet"]
        alt_ft = track["altitude_feet"]
        speed_ft_s = track["speed_feet_per_second"]
        bank_rad = track["bank_angle_radians"]
        pitch_rad = track["pitch_angle_radians"]
        heading_rad = track["heading_angle_radians"]

        cos_h = math.cos(heading_offset_rad)
        sin_h = math.sin(heading_offset_rad)

        observations: list[FlightObservationSchema] = []
        for _, (t, n_ft, e_ft, alt_ft_val, speed_ft_s_val, bank_val, pitch_val, heading_val) in enumerate(
            zip(times, north_ft, east_ft, alt_ft, speed_ft_s, bank_rad, pitch_rad, heading_rad)
        ):
            # Rotate in local frame then convert feet → metres → degrees
            rotated_n = float(n_ft) * cos_h - float(e_ft) * sin_h
            rotated_e = float(n_ft) * sin_h + float(e_ft) * cos_h
            dn_m = rotated_n * FEET_TO_METERS
            de_m = rotated_e * FEET_TO_METERS

            if origin_lat is not None and origin_lon is not None:
                lat = origin_lat + dn_m / _METERS_PER_DEG_LAT
                lon = origin_lon + de_m / _meters_per_deg_lon(origin_lat)
            else:
                lat = dn_m / _METERS_PER_DEG_LAT
                lon = de_m / _meters_per_deg_lon(0.0)

            altitude_mm = float(alt_ft_val) * FEET_TO_MM
            timestamp = int(base_time.shift(seconds=float(t)).float_timestamp * 1_000_000)

            selected_sensor_id = random.choice(sensor_ids) if use_multiple_sensors and len(sensor_ids) > 1 else sensor_ids[0]

            metadata = {
                "sensor_id": str(selected_sensor_id),
                "speed_feet_per_second": float(speed_ft_s_val),
                "bank_angle_radians": float(bank_val),
                "pitch_angle_radians": float(pitch_val),
                "heading_angle_radians": float(heading_val + heading_offset_rad),
            }

            observations.append(
                FlightObservationSchema(
                    lat_dd=lat,
                    lon_dd=lon,
                    altitude_mm=altitude_mm,
                    traffic_source=0,
                    source_type=0,
                    icao_address=icao_address,
                    timestamp=timestamp,
                    metadata=metadata,
                )
            )

        return observations

    @internal_step("Generate Bayesian Simulation Air Traffic Data with latency issues", phase=FlightPhase.PRE_FLIGHT)
    async def generate_bayesian_sim_air_traffic_data_with_sensor_latency_issues(
        self,
        config_path: str | None = None,
        duration: int | None = None,
    ) -> list[FlightObservationSchema]:
        """
        This method modifies the retrieved simulation data by changing the timestamp and adding latency to the observed dataset.
        Latency is simulated by randomly removing some observations and randomly shifting the timestamps of some observations
        to be earlier or later than the actual timestamp, mimicking real-world sensor latency issues.
        """
        step_result = await self.generate_bayesian_sim_air_traffic_data(config_path=config_path, duration=duration)
        flight_observations = step_result.result

        LATENCY_PROBABILITY = 0.1  # 10% chance to have latency issues
        TIMESTAMP_SHIFT_RANGE_SECONDS = (-1, 2.5)  # Shift timestamps by -5 to +5 seconds

        modified_flight_observations = []
        for obs in flight_observations:
            if random.random() < LATENCY_PROBABILITY:
                # Simulate latency by removing some observations
                if random.random() < 0.5:  # 50% chance to remove observation
                    continue
                # Simulate timestamp shift
                shift_seconds = random.uniform(*TIMESTAMP_SHIFT_RANGE_SECONDS)
                obs = obs.model_copy(update={"timestamp": obs.timestamp + int(shift_seconds * 1_000_000)})
            modified_flight_observations.append(obs)

        return modified_flight_observations
