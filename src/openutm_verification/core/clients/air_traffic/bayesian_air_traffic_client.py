from __future__ import annotations

import uuid
from uuid import UUID

from cam_track_gen import TrackGenerationSession, get_available_model_files
from loguru import logger

from openutm_verification.core.clients.air_traffic.base_client import (
    BayesianAirTrafficClient,
    BayesianAirTrafficSettings,
)
from openutm_verification.core.clients.flight_blender.base_client import (
    BaseBlenderAPIClient,
)
from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.simulator.models.flight_data_types import FlightObservationSchema


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
        # duration_s = int(duration or self.settings.simulation_duration_seconds or 30)

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
        tracks = session.generate_tracks(number_of_tracks=3, simulation_duration_seconds=100)

        if tracks:
            logger.info(f"Successfully generated {len(tracks)} tracks.")
            # You can now work with the generated track data
            first_track = tracks[0]
            logger.info(f"First track has {len(first_track['time'])} data points.")
        else:
            logger.info("Track generation failed.")

        return []  # Placeholder return
