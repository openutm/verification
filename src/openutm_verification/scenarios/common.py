import json
from pathlib import Path
from typing import Any, List

from loguru import logger

from openutm_verification.simulator.flight_declaration import FlightDeclarationGenerator
from openutm_verification.simulator.geo_json_telemetry import GeoJSONFlightsSimulator
from openutm_verification.simulator.models.flight_data_types import (
    GeoJSONFlightsSimulatorConfiguration,
)

DEFAULT_TELEMETRY_DURATION = 30  # seconds


def generate_flight_declaration(config_path: str) -> Any:
    """Generate a flight declaration from the config file at the given path."""
    try:
        generator = FlightDeclarationGenerator(bounds_path=Path(config_path))
        return generator.generate()
    except Exception as e:
        logger.error(f"Failed to generate flight declaration from {config_path}: {e}")
        raise


def generate_telemetry(config_path: str, duration: int = DEFAULT_TELEMETRY_DURATION) -> List[Any]:
    """Generate telemetry states from the GeoJSON config file at the given path."""
    try:
        logger.debug(f"Generating telemetry states from {config_path} for duration {duration} seconds")
        with open(config_path, "r", encoding="utf-8") as f:
            geojson_data = json.load(f)

        simulator_config = GeoJSONFlightsSimulatorConfiguration(geojson=geojson_data)
        simulator = GeoJSONFlightsSimulator(simulator_config)

        simulator.generate_flight_grid_and_path_points(altitude_of_ground_level_wgs_84=120)
        return simulator.generate_states(duration=duration)
    except Exception as e:
        logger.error(f"Failed to generate telemetry states from {config_path}: {e}")
        raise


def get_geo_fence_path(geo_fence_filename: str) -> str:
    """Helper to get the full path to a geo-fence file."""
    parent_dir = Path(__file__).parent.resolve()
    return str(parent_dir / f"../assets/aoi_geo_fence_samples/{geo_fence_filename}")
