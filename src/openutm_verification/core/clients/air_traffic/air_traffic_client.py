import json
from typing import Optional

from loguru import logger

from openutm_verification.core.clients.air_traffic.base_client import (
    AirTrafficSettings,
    BaseAirTrafficAPIClient,
)
from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.simulator.geo_json_telemetry import (
    GeoJSONAirtrafficSimulator,
)
from openutm_verification.simulator.models.flight_data_types import (
    AirTrafficGeneratorConfiguration,
)


class AirTrafficClient(BaseAirTrafficAPIClient):
    """Client for fetching live flight data from OpenSky Network and generating simulated air traffic data."""

    def __init__(self, settings: AirTrafficSettings):
        super().__init__(settings)

    @scenario_step("Generate Simulated Air Traffic Data")
    def generate_simulated_air_traffic_data(
        self,
        config_path: Optional[str] = None,
        duration: Optional[int] = None,
    ) -> Optional[list[dict]]:
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
        duration = duration or self.settings.simulation_duration_seconds

        try:
            logger.debug(f"Generating telemetry states from {config_path} for duration {duration} seconds")
            with open(config_path, "r", encoding="utf-8") as file_handle:
                geojson_data = json.load(file_handle)

            simulator_config = AirTrafficGeneratorConfiguration(geojson=geojson_data)
            simulator = GeoJSONAirtrafficSimulator(simulator_config)

            return simulator.generate_air_traffic_data(duration=duration)

        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to generate telemetry states from {config_path}: {exc}")
            raise
