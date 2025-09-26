import json
import random
import sys
from pathlib import Path
from typing import List, Optional

import arrow
from loguru import logger
from pyproj import Geod, Transformer
from shapely.geometry import LineString, Point, Polygon, box, mapping, shape
from shapely.geometry.base import BaseGeometry
from uas_standards.astm.f3411.v22a.api import (
    HorizontalAccuracy,
    RIDAircraftPosition,
    RIDAircraftState,
    RIDFlightDetails,
    RIDHeight,
    Time,
    VerticalAccuracy,
)

from openutm_verification.simulator.models.flight_data_types import (
    FlightRecordCollection,
    FullFlightRecord,
    GeoJSONFlightsSimulatorConfiguration,
)
from openutm_verification.simulator.models.geo_json_models import (
    GeoJSONFeatureCollection,
    ValidatedFlightPath,
)
from openutm_verification.simulator.models.utils import (
    FlightPoint,
    GridCellFlight,
)
from openutm_verification.simulator.operator_flight_data import (
    OperatorFlightDataGenerator,
)


class GeoJSONFlightsSimulator:
    """Generate a flight path given a GeoJSON LineString with validated inputs."""

    def __init__(self, config: GeoJSONFlightsSimulatorConfiguration) -> None:
        self.config: GeoJSONFlightsSimulatorConfiguration = config
        self.reference_time: arrow.Arrow = arrow.get(config.reference_time.datetime)
        self.flight_start_shift_time: int = config.flight_start_shift
        self.random: random.Random = random.Random() if config.random_seed is None else random.Random(x=config.random_seed)

        self.utm_zone: int = config.utm_zone
        self.altitude_agl: float = 50.0

        self.flight: Optional[FullFlightRecord] = None

        self.geod: Geod = Geod(ellps="WGS84")

        self.flights: list[FullFlightRecord] = []
        self.grid_cells_flight_tracks: list[GridCellFlight] = []

        # Cache pyproj transformers for performance
        wgs84 = "EPSG:4326"
        utm = f"+proj=utm +zone={self.utm_zone} +ellps=WGS84 +datum=WGS84"
        self._tx_wgs84_to_utm = Transformer.from_crs(wgs84, utm, always_xy=True)
        self._tx_utm_to_wgs84 = Transformer.from_crs(utm, wgs84, always_xy=True)

        # Validate input GeoJSON and precompute derived values via Pydantic models
        vfp: ValidatedFlightPath = ValidatedFlightPath.from_feature_collection(self.config.geojson)
        # Assign derived fields used by downstream logic
        self.line_string: LineString = LineString(vfp.path_points)
        self.box: Polygon = box(*vfp.box_bounds)
        self.half_box: Polygon = box(*vfp.half_box_bounds)
        self.center_point: Point = Point(*vfp.center)
        self.bounds: tuple[float, float, float, float] = vfp.bounds
        # Convert to shapely Points for speed/bearing computations later
        self.flight_path_points: list[Point] = [Point(lon, lat) for lon, lat in vfp.path_points]
        logger.info(f"Validated LineString length: {vfp.line_length_m:.1f} m, generated {len(self.flight_path_points)} path points")

    def generate_flight_speed_bearing(self, adjacent_points: list[Point], delta_time_secs: int) -> tuple[float, float]:
        """Generate speed (m/s) and bearing between two adjacent Points."""
        first_point = adjacent_points[0]
        second_point = adjacent_points[1]

        fwd_azimuth, _, adjacent_point_distance_mts = self.geod.inv(first_point.x, first_point.y, second_point.x, second_point.y)
        speed_mts_per_sec = round(adjacent_point_distance_mts / delta_time_secs, 2)
        # Normalize azimuth to [0, 360)
        fwd_azimuth = (fwd_azimuth + 360.0) % 360.0
        return speed_mts_per_sec, fwd_azimuth

    def utm_converter(self, shapely_shape: BaseGeometry, inverse: bool = False) -> BaseGeometry:
        """Convert between WGS84 (lon/lat) and UTM coordinates for buffering."""
        transformer = self._tx_utm_to_wgs84 if inverse else self._tx_wgs84_to_utm

        gi = shapely_shape.__geo_interface__
        gtype: str = gi["type"]
        coords = gi["coordinates"]

        def _tx_pair(pair):
            x, y = pair
            return transformer.transform(x, y)

        if gtype == "Polygon":
            new_coords = [[_tx_pair(pt) for pt in ring] for ring in coords]
        elif gtype == "Point":
            new_coords = _tx_pair(coords)
        elif gtype == "LineString":
            new_coords = [_tx_pair(pt) for pt in coords]
        else:
            raise RuntimeError(f"Unexpected geo_interface type: {gtype}")

        return shape({"type": gtype, "coordinates": tuple(new_coords)})

    def generate_flight_grid_and_path_points(self, altitude_of_ground_level_wgs_84: float, *, loop_path: bool = False) -> None:
        flight_points_with_altitude: list[FlightPoint] = []
        logger.info(f"Generating flight grid and path points at altitude {altitude_of_ground_level_wgs_84} meters")
        all_grid_cell_tracks = []
        if not self.flight_path_points:
            raise RuntimeError("No flight path points available")
        n_points = len(self.flight_path_points)
        if n_points < 2 and not loop_path:
            raise ValueError("Path must have at least 2 points for non-looped paths")
        end = n_points if loop_path else max(n_points - 1, 0)
        for cur_coord in range(0, end):
            next_coord = (cur_coord + 1) % n_points if loop_path else cur_coord + 1
            adjacent_points = [
                self.flight_path_points[cur_coord],
                self.flight_path_points[next_coord],
            ]
            speed, bearing = self.generate_flight_speed_bearing(adjacent_points=adjacent_points, delta_time_secs=1)

            flight_points_with_altitude.append(
                FlightPoint(
                    lat=self.flight_path_points[cur_coord].y,
                    lng=self.flight_path_points[cur_coord].x,
                    alt=altitude_of_ground_level_wgs_84,
                    speed=speed,
                    bearing=bearing,
                )
            )
        if self.bounds is None:
            raise RuntimeError("Bounds must be set before generating grid cells")
        bounds_box = box(*self.bounds)

        all_grid_cell_tracks.append(GridCellFlight(bounds=bounds_box, track=flight_points_with_altitude))

        self.grid_cells_flight_tracks = all_grid_cell_tracks

    def generate_flight_details(self, flight_id: str) -> RIDFlightDetails:
        """
        Generate details of flights and operator details for a flight.
        This data is required for identifying flight, operator and operation.
        """
        my_flight_details_generator = OperatorFlightDataGenerator(self.random)
        operator_location = my_flight_details_generator.generate_operator_location(centroid=self.center_point)
        return RIDFlightDetails(
            id=flight_id,
            serial_number=my_flight_details_generator.generate_serial_number(),
            operation_description=my_flight_details_generator.generate_operation_description(),
            operator_location=operator_location,
            operator_id=my_flight_details_generator.generate_operator_id(),
            registration_number=my_flight_details_generator.generate_registration_number(),
        )

    def generate_states(self, duration: int, loop_path: bool = False) -> List[RIDAircraftState]:
        """
        Generate rid_state objects that can be submitted as flight telemetry.
        """
        all_flight_telemetry: List[List[RIDAircraftState]] = []
        flight_track_details: dict[int, dict[str, int]] = {}
        flight_current_index: dict[int, int] = {}
        num_flights = len(self.grid_cells_flight_tracks)
        logger.info(f"Number of flights: {num_flights}")
        time_increment_seconds = 1
        now = self.reference_time
        now_isoformat = now.isoformat()
        for i in range(num_flights):
            flight_positions_len = len(self.grid_cells_flight_tracks[i].track)
            if i not in flight_track_details:
                flight_track_details[i] = {}
            flight_track_details[i]["track_length"] = flight_positions_len
            flight_current_index[i] = 0
            all_flight_telemetry.append([])

        timestamp = now
        for _ in range(duration):
            timestamp = timestamp.shift(seconds=time_increment_seconds)

            for k in range(num_flights):
                timestamp_isoformat = timestamp.shift(seconds=k * self.flight_start_shift_time).isoformat()
                track_len = flight_track_details[k]["track_length"]
                if track_len == 0:
                    continue
                if loop_path:
                    idx = flight_current_index[k] % track_len
                else:
                    idx = min(flight_current_index[k], track_len - 1)
                flight_point = self.grid_cells_flight_tracks[k].track[idx]
                aircraft_position = RIDAircraftPosition(
                    lat=flight_point.lat,
                    lng=flight_point.lng,
                    alt=flight_point.alt,
                    accuracy_h=HorizontalAccuracy.HAUnknown,
                    accuracy_v=VerticalAccuracy.VAUnknown,
                    extrapolated=False,
                )
                aircraft_height = RIDHeight(distance=self.altitude_agl, reference="TakeoffLocation")

                rid_aircraft_state = RIDAircraftState(
                    timestamp=Time(value=timestamp_isoformat, format="RFC3339"),
                    operational_status="Airborne",
                    position=aircraft_position,
                    height=aircraft_height,
                    track=flight_point.bearing,
                    speed=flight_point.speed,
                    timestamp_accuracy=0.0,
                    speed_accuracy="SA3mps",
                    vertical_speed=0.0,
                )

                all_flight_telemetry[k].append(rid_aircraft_state)
                flight_current_index[k] = flight_current_index[k] + 1

        flights: List[FullFlightRecord] = []
        for m in range(num_flights):
            record = FullFlightRecord(
                reference_time=now_isoformat,
                states=all_flight_telemetry[m],
                flight_details=self.generate_flight_details(flight_id=str(m)),
                aircraft_type="Helicopter",
            )
            flights.append(record)
        self.flights = flights

        # Return states for flight 0 for in-memory use
        return all_flight_telemetry[0] if all_flight_telemetry else []

    def to_jsonable_state(self, state: RIDAircraftState) -> dict:
        """Convert a RIDAircraftState to a JSON-serializable dict."""
        return json.loads(json.dumps(state))

    def to_jsonable_states(self, states: List[RIDAircraftState]) -> List[dict]:
        """Convert a list of RIDAircraftState to a list of JSON-serializable dicts."""
        return [self.to_jsonable_state(state) for state in states]

    def generate_telemetry_payload(self, duration: int, loop_path: bool = False) -> dict:
        """Generate a telemetry payload dict with reference_time and current_states.

        Args:
            duration: Duration in seconds.
            loop_path: Whether to loop the path.

        Returns:
            Dict with 'reference_time' and 'current_states'.
        """
        states = self.generate_states(duration, loop_path)
        jsonable_states = self.to_jsonable_states(states)
        return {
            "reference_time": self.reference_time.isoformat(),
            "current_states": jsonable_states,
        }


def generate_aircraft_states(
    config: GeoJSONFlightsSimulatorConfiguration,
) -> FlightRecordCollection:
    my_path_generator = GeoJSONFlightsSimulator(config)

    my_path_generator.generate_flight_grid_and_path_points(altitude_of_ground_level_wgs_84=config.altitude_of_ground_level_wgs_84)

    my_path_generator.generate_states(duration=30)
    flights = my_path_generator.flights

    result = FlightRecordCollection(flights=flights)

    # Already the correct type; no need to re-parse via ImplicitDict
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run GeoJSON Flight Simulator")
    parser.add_argument("--config", type=str, default="config.json", help="Path to config file")
    parser.add_argument("--duration", type=int, default=30, help="Duration of simulation in seconds")
    parser.add_argument("--loop-path", action="store_true", help="Loop the flight path")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory for files")
    args = parser.parse_args()

    # Load configuration from config.json
    config_file_path = Path(args.config)

    logger.info(f"Loading configuration from: {config_file_path}")
    if config_file_path.exists():
        with config_file_path.open("r", encoding="utf-8") as config_file:
            config_data = json.load(config_file)

    else:
        logger.error("Config file not found. Please create a config.json file.")
        sys.exit(1)

    # Validate the JSON config and its GeoJSON payload
    cfg = GeoJSONFeatureCollection.model_validate(config_data)
    geojson_data = cfg.model_dump(mode="json")
    my_flight_generator = GeoJSONFlightsSimulator(
        config=GeoJSONFlightsSimulatorConfiguration(
            reference_time=arrow.utcnow(),
            geojson=geojson_data,
            altitude_of_ground_level_wgs_84=500,
            random_seed=None,
        )
    )
    # Use the configured altitude consistently
    my_flight_generator.generate_flight_grid_and_path_points(
        altitude_of_ground_level_wgs_84=my_flight_generator.config.altitude_of_ground_level_wgs_84, loop_path=args.loop_path
    )

    my_flight_generator.generate_states(duration=args.duration, loop_path=args.loop_path)
    # Add the bounding box as GeoJSON to the flight declaration
    # Create the output directory if it does not exist
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory created or already exists: {output_dir}")

    bbox_file = output_dir / "flight_declaration_bounding_box.json"
    half_box_bbox_file = output_dir / "flight_declaration_half_bounding_box.json"
    flight_data_file = output_dir / "flight_data.json"

    if my_flight_generator.half_box is None or my_flight_generator.box is None:
        raise RuntimeError("Bounding boxes were not generated")
    half_bbox_geojson = mapping(my_flight_generator.half_box)
    bbox_geojson = mapping(my_flight_generator.box)

    logger.info("Generated GeoJSON for bounding boxes.")
    # Persist bounding boxes
    with bbox_file.open("w", encoding="utf-8") as f:
        json.dump(bbox_geojson, f, indent=2)
    with half_box_bbox_file.open("w", encoding="utf-8") as f:
        json.dump(half_bbox_geojson, f, indent=2)

    logger.info(f"Number of flights generated: {len(my_flight_generator.flights)}")
    # Generate telemetry payload using the serialization helpers
    payload = my_flight_generator.generate_telemetry_payload(duration=args.duration, loop_path=args.loop_path)
    with flight_data_file.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    logger.info(f"Telemetry payload saved to: {flight_data_file}")
