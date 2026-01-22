import json
import uuid
from pathlib import Path

from implicitdict import StringBasedDateTime
from loguru import logger
from uas_standards.astm.f3411.v22a.api import RIDAircraftState

from openutm_verification.core.execution.scenario_runner import scenario_step
from openutm_verification.simulator.flight_declaration import FlightDeclarationGenerator
from openutm_verification.simulator.geo_json_telemetry import GeoJSONFlightsSimulator
from openutm_verification.simulator.models.declaration_models import FlightDeclaration, FlightDeclarationViaOperationalIntent
from openutm_verification.simulator.models.flight_data_types import (
    GeoJSONFlightsSimulatorConfiguration,
)

DEFAULT_TELEMETRY_DURATION = 30  # seconds


def generate_flight_declaration(config_path: str) -> FlightDeclaration:
    """Generate a flight declaration from the config file at the given path."""
    try:
        generator = FlightDeclarationGenerator(bounds_path=Path(config_path))
        return generator.generate()
    except Exception as e:
        logger.error(f"Failed to generate flight declaration from {config_path}: {e}")
        raise


def generate_flight_declaration_via_operational_intent(config_path: str) -> FlightDeclarationViaOperationalIntent:
    """Generate a flight declaration via operational intent from the config file at the given path."""
    try:
        generator = FlightDeclarationGenerator(bounds_path=Path(config_path))
        return generator.generate_via_operational_intent()
    except Exception as e:
        logger.error(f"Failed to generate flight declaration via operational intent from {config_path}: {e}")
        raise


def generate_telemetry(config_path: str, duration: int = DEFAULT_TELEMETRY_DURATION, reference_time: str | None = None) -> list[RIDAircraftState]:
    """Generate telemetry states from the GeoJSON config file at the given path."""
    try:
        logger.debug(f"Generating telemetry states from {config_path} for duration {duration} seconds")
        with open(config_path, "r", encoding="utf-8") as f:
            geojson_data = json.load(f)

        config_args = {"geojson": geojson_data}
        if reference_time:
            config_args["reference_time"] = StringBasedDateTime(reference_time)

        simulator_config = GeoJSONFlightsSimulatorConfiguration(**config_args)
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


@scenario_step("Generate UUID")
async def generate_uuid() -> str:
    """Generates a random UUID."""
    return str(uuid.uuid4())
