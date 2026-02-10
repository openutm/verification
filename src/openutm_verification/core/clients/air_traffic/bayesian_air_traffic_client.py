from __future__ import annotations

import random
import uuid
from uuid import UUID

import arrow
from cam_track_gen import TrackGenerationSession, TrackResultData, get_available_model_files
from loguru import logger
from pyproj import Transformer

from openutm_verification.core.clients.air_traffic.base_client import (
    BayesianAirTrafficClient,
    BayesianAirTrafficSettings,
)
from openutm_verification.core.clients.flight_blender.base_client import (
    BaseBlenderAPIClient,
)
from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.simulator.models.flight_data_types import FlightObservationSchema


def random_icao():
    n = random.randrange(1, 0xFFFFFF)  # excludes 0x000000 and 0xFFFFFF
    return f"{n:06X}"


FEET_TO_METERS = 0.3048
FEET_TO_MM = FEET_TO_METERS * 1000

# EPSG 3347 (NAD83 / Statistics Canada Lambert) -> EPSG 4326 (WGS84)
_transformer = Transformer.from_crs("EPSG:3347", "EPSG:4326", always_xy=True)


class BayesianTrafficClient(BayesianAirTrafficClient, BaseBlenderAPIClient):
    """Bayesian client that loads and runs a .scn file and samples aircraft states at 1 Hz."""

    def __init__(self, settings: BayesianAirTrafficSettings):
        BayesianAirTrafficClient.__init__(self, settings)
        # Initialize BaseBlenderAPIClient with dummy values since we don't use it for HTTP requests here
        # but we inherit from it. Ideally, we should refactor to composition over inheritance.
        BaseBlenderAPIClient.__init__(self, base_url="", credentials={})

    @scenario_step("Generate Bayesian Simulation Air Traffic Data")
    async def generate_bayesian_sim_air_traffic_data(
        self,
        config_path: str | None = None,
        duration: int | None = None,
    ) -> list[list[FlightObservationSchema]]:
        """Run Bayesian scenario and sample aircraft state every second.

        Args:
            config_path: Path to .scn scenario file. Defaults to settings.simulation_config_path.
            duration: Simulation duration in seconds. Defaults to settings.simulation_duration_seconds (expected 30).
        Returns:
            list[list[FlightObservationSchema]]: outer list per aircraft (icao_address),
            inner list is time-series sampled at 1 Hz.
        """

        # scn_path = config_path or self.settings.simulation_config_path
        duration_in_seconds = int(duration or self.settings.simulation_duration_seconds or 30)
        number_of_aircraft = self.settings.number_of_aircraft or 3
        sensor_ids = self.settings.sensor_ids

        try:
            # create a list of UUIDs with at least one UUID if session_ids is empty
            sensor_ids = [UUID(x) for x in sensor_ids] if sensor_ids else [uuid.uuid4()]
        except ValueError as exc:
            logger.error(f"Invalid sensor ID in configuration, it should be a valid UUID: {exc}")
            raise
        # current_sensor_id = sensor_ids[0]

        # List the models bundled with the library
        available_models = get_available_model_files()
        logger.info(f"Available models from cam-track-gen: {available_models}")

        if not available_models:
            logger.info("No models found.")
            return

        # Use one of the models
        model_filename = "Light_Aircraft_Below_10000_ft_Data.mat"
        logger.info(f"\nUsing model: {model_filename}")

        # Create a session
        session = TrackGenerationSession.create_from_file(model_filename)

        if session is None:
            logger.info("Failed to create a session.")
            return

        # Generate a few tracks
        logger.info("Generating tracks...")
        tracks = session.generate_tracks(number_of_tracks=number_of_aircraft, simulation_duration_seconds=duration_in_seconds)

        if not tracks:
            logger.info("Track generation failed.")
            return []

        logger.info(f"Successfully generated {len(tracks)} tracks.")

        base_timestamp = int(arrow.utcnow().timestamp())
        all_observations: list[list[FlightObservationSchema]] = []

        for track_idx, track in enumerate(tracks):
            icao_address = random_icao()

            observations = self._convert_track_to_observations(
                track=track,
                icao_address=icao_address,
                base_timestamp=base_timestamp,
            )
            all_observations.append(observations)
            logger.info(f"Track {track_idx} ({icao_address}): {len(observations)} observations")
        logger.info(
            f"Generated observations for {len(all_observations)} tracks, with {sum(len(obs) for obs in all_observations)} total observations."
        )
        logger.info(f"First observation altitude: {all_observations[0][0].icao_address}")

        return all_observations

    @staticmethod
    def _convert_track_to_observations(
        track: TrackResultData,
        icao_address: str,
        base_timestamp: int,
    ) -> list[FlightObservationSchema]:
        """Convert a raw track dict from cam-track-gen to FlightObservationSchema list.

        The track contains positions in EPSG 3347 (NAD83 / Statistics Canada Lambert)
        with values in feet. This method converts to WGS84 lat/lon and altitude in mm.
        """
        times = track["time"]
        north_ft = track["north_position_feet"]
        east_ft = track["east_position_feet"]
        alt_ft = track["altitude_feet"]
        speed_ft_s = track["speed_feet_per_second"]
        bank_rad = track["bank_angle_radians"]
        pitch_rad = track["pitch_angle_radians"]
        heading_rad = track["heading_angle_radians"]

        # Convert feet to meters for coordinate transformation
        east_m = east_ft * FEET_TO_METERS
        north_m = north_ft * FEET_TO_METERS

        # Transform from EPSG 3347 (easting, northing) to WGS84 (lon, lat)
        longitudes, latitudes = _transformer.transform(east_m, north_m)

        observations: list[FlightObservationSchema] = []
        for i, (t, lat, lon, alt_ft_val, speed_ft_s_val, bank_val, pitch_val, heading_val) in enumerate(
            zip(times, latitudes, longitudes, alt_ft, speed_ft_s, bank_rad, pitch_rad, heading_rad)
        ):
            altitude_mm = float(alt_ft_val) * FEET_TO_MM
            timestamp = base_timestamp + int(round(float(t)))

            metadata = {
                "speed_feet_per_second": float(speed_ft_s_val),
                "bank_angle_radians": float(bank_val),
                "pitch_angle_radians": float(pitch_val),
                "heading_angle_radians": float(heading_val),
            }

            observations.append(
                FlightObservationSchema(
                    lat_dd=float(lat),
                    lon_dd=float(lon),
                    altitude_mm=altitude_mm,
                    traffic_source=0,
                    source_type=0,
                    icao_address=icao_address,
                    timestamp=timestamp,
                    metadata=metadata,
                )
            )
        logger.info(f"Converted track to observations. Generated {len(observations)} observations.")

        return observations

    @scenario_step("Generate Bayesian Simulation Air Traffic Data with latency issues")
    async def generate_bayesian_sim_air_traffic_data_with_sensor_latency_issues(
        self,
        config_path: str | None = None,
        duration: int | None = None,
    ) -> list[list[FlightObservationSchema]]:
        """ This method generates """
        flight_observations = self.generate_bayesian_sim_air_traffic_data(config_path = config_path, duration = duration)

        # This method modifies the retrieved simulation data by changing the timestamp and adding latency to the observed dataset

        # TODO: Implement the logic s

        return flight_observations
