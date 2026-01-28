import json
import uuid
from uuid import UUID

from loguru import logger

from openutm_verification.core.clients.air_traffic.base_client import (
    AirTrafficSettings,
    BaseAirTrafficAPIClient,
)
from openutm_verification.core.clients.flight_blender.base_client import (
    BaseBlenderAPIClient,
)
from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.simulator.geo_json_telemetry import (
    GeoJSONAirtrafficSimulator,
)
from openutm_verification.simulator.models.flight_data_types import (
    AirTrafficGeneratorConfiguration,
    FlightObservationSchema,
)


class AirTrafficClient(BaseAirTrafficAPIClient, BaseBlenderAPIClient):
    """Client for fetching live flight data from OpenSky Network and generating simulated air traffic data."""

    def __init__(self, settings: AirTrafficSettings):
        BaseAirTrafficAPIClient.__init__(self, settings)
        # Initialize BaseBlenderAPIClient with dummy values since we don't use it for HTTP requests here
        # but we inherit from it. Ideally, we should refactor to composition over inheritance.
        BaseBlenderAPIClient.__init__(self, base_url="", credentials={})

    @scenario_step("Generate Simulated Air Traffic Data")
    async def generate_simulated_air_traffic_data(
        self,
        config_path: str | None = None,
        duration: int | None = None,
    ) -> list[list[FlightObservationSchema]]:
        """Generate simulated air traffic data from GeoJSON configuration.

        Loads GeoJSON data from the specified config path and uses it to generate
        simulated flight observations for the given duration. If no config path
        or duration is provided, uses the default settings from the client configuration.

        Args:
            config_path: Path to the GeoJSON configuration file. Defaults to settings value.
            duration: Duration in seconds for which to generate data. Defaults to settings value.

        Returns:
            List of simulated flight observation dictionaries, or None if generation fails.
        """
        config_path = config_path or self.settings.simulation_config_path
        duration = duration or self.settings.simulation_duration
        number_of_aircraft = self.settings.number_of_aircraft
        sensor_ids = self.settings.sensor_ids

        try:
            # create a list of UUIDs with at least one UUID if session_ids is empty
            sensor_ids = [UUID(x) for x in sensor_ids] if sensor_ids else [uuid.uuid4()]
        except ValueError as exc:
            logger.error(f"Invalid sensor ID in configuration, it should be a valid UUID: {exc}")
            raise

        try:
            logger.debug(f"Generating telemetry states from {config_path} for duration {duration} seconds")
            with open(config_path, "r", encoding="utf-8") as file_handle:
                geojson_data = json.load(file_handle)

            simulator_config = AirTrafficGeneratorConfiguration(geojson=geojson_data)
            simulator = GeoJSONAirtrafficSimulator(simulator_config)

            return simulator.generate_air_traffic_data(
                duration=duration,
                number_of_aircraft=number_of_aircraft,
                sensor_ids=sensor_ids,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to generate telemetry states from {config_path}: {exc}")
            raise
