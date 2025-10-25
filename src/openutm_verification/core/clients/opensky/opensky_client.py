import json
from dataclasses import asdict
from typing import Optional

import pandas as pd
from loguru import logger
from pydantic import BaseModel

from openutm_verification.core.clients.opensky.base_client import (
    BaseOpenSkyAPIClient,
    OpenSkySettings,
)
from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.simulator.geo_json_telemetry import (
    GeoJSONAirtrafficSimulator,
)
from openutm_verification.simulator.models.flight_data_types import (
    AirTrafficGeneratorConfiguration,
    FlightObservationSchema,
)


class SingleObservation(BaseModel):
    """Pydantic model for storing flight observation details."""

    timestamp: int
    lat_dd: float
    lon_dd: float
    altitude_mm: float
    traffic_source: int
    source_type: int
    icao_address: str
    metadata: Optional[dict] = None


class OpenSkyClient(BaseOpenSkyAPIClient):
    """Client for fetching and processing OpenSky Network flight data."""

    # OpenSky API response column names
    COLUMN_NAMES = [
        "icao24",
        "callsign",
        "origin_country",
        "time_position",
        "last_contact",
        "long",
        "lat",
        "baro_altitude",
        "on_ground",
        "velocity",
        "true_track",
        "vertical_rate",
        "sensors",
        "geo_altitude",
        "squawk",
        "spi",
        "position_source",
    ]

    def __init__(self, settings: OpenSkySettings):
        super().__init__(settings)
        self._viewport_bounds = self._calculate_viewport_bounds()

    def _calculate_viewport_bounds(self) -> dict:
        """Calculate viewport boundaries for API requests."""
        lat_min = min(self.settings.viewport[0], self.settings.viewport[2])
        lat_max = max(self.settings.viewport[0], self.settings.viewport[2])
        lng_min = min(self.settings.viewport[1], self.settings.viewport[3])
        lng_max = max(self.settings.viewport[1], self.settings.viewport[3])

        return {
            "lamin": lat_min,
            "lomin": lng_min,
            "lamax": lat_max,
            "lomax": lng_max,
        }

    def generate_air_traffic_data(self, config_path: str, duration: int = 30) -> list[dict]:
        """Generate air traffic telemetry states from the config file at the given path."""
        try:
            logger.debug(f"Generating telemetry states from {config_path} for duration {duration} seconds")
            with open(config_path, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            simulator_config = AirTrafficGeneratorConfiguration(geojson=geojson_data)
            simulator = GeoJSONAirtrafficSimulator(simulator_config)

            generated_airtraffic_data: list[FlightObservationSchema] = simulator.generate_air_traffic_data(duration=duration)
            return [asdict(obs) for obs in generated_airtraffic_data]

        except Exception as e:
            logger.error(f"Failed to generate telemetry states from {config_path}: {e}")
            raise

    @scenario_step("Generate Simulated Air Traffic Data")
    def generate_simulated_air_traffic_data(self) -> Optional[list[dict]]:
        return self.generate_air_traffic_data(
            config_path=self.settings.simulation_config_path,
            duration=self.settings.simulation_duration_seconds,
        )

    def fetch_states_data(self) -> Optional[pd.DataFrame]:
        """Fetch current flight states from OpenSky Network."""
        try:
            response = self.get("/states/all", params=self._viewport_bounds)
            data = response.json()

            if not data.get("states"):
                logger.warning("No flight states data found in OpenSky response")
                return None

            flight_df = pd.DataFrame(data["states"], columns=self.COLUMN_NAMES).fillna("No Data")

            logger.info(f"Fetched {len(flight_df)} flight states from OpenSky")
            return flight_df

        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to fetch states data: {e}")
            return None

    def process_flight_data(self, flight_df: pd.DataFrame) -> list[dict]:
        """Process flight DataFrame into observation format."""
        observations = []
        for _, row in flight_df.iterrows():
            altitude = 0.0 if row["baro_altitude"] == "No Data" else row["baro_altitude"]

            # Create observation using Pydantic model
            observation = SingleObservation(
                timestamp=int(row["time_position"]),
                icao_address=str(row["icao24"]),
                traffic_source=2,  # ADS-B traffic source
                source_type=1,  # Aircraft
                lat_dd=float(row["lat"]),
                lon_dd=float(row["long"]),
                altitude_mm=float(altitude),
                metadata={"velocity": row["velocity"]},
            )
            observations.append(observation.model_dump())
        logger.info(f"Processed {len(observations)} observations")
        return observations

    def fetch_and_process_data(self) -> Optional[list[dict]]:
        """Fetch flight data and process into observations."""
        flight_df = self.fetch_states_data()
        if flight_df is None or flight_df.empty:
            return None

        return self.process_flight_data(flight_df)

    @scenario_step("Fetch OpenSky Data")
    def fetch_data(self):
        return self.fetch_and_process_data()
