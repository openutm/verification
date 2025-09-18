import json
import logging
import os
import random
import sys
from datetime import timedelta
from typing import List

import arrow
import shapely.geometry
from geojson import Feature, FeatureCollection
from geojson import LineString as GeoJSONLineString
from geojson import Point as GeoJSONPoint
from geojson import Polygon as GeoJSONPolygon
from implicitdict import ImplicitDict
from pyproj import Geod, Proj, Transformer
from shapely.geometry import LineString, Point
from uas_standards.astm.f3411.v22a.api import (
    HorizontalAccuracy,
    LatLngPoint,
    RIDAircraftPosition,
    RIDAircraftState,
    RIDFlightDetails,
    RIDHeight,
    Time,
    VerticalAccuracy,
)

from openutm_verification.simulator.flight_data import (
    FlightRecordCollection,
    FullFlightRecord,
    GeoJSONFlightsSimulatorConfiguration,
)
from openutm_verification.simulator.operator_flight_details import (
    OperatorFlightDataGenerator,
)
from openutm_verification.simulator.utils import (
    FlightPoint,
    GridCellFlight,
    QueryBoundingBox,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Log to console
        logging.FileHandler("simulator.log", mode="w"),  # Log to a file
    ],
)

# Create a logger instance
logger = logging.getLogger(__name__)


class GeoJSONFlightsSimulator(object):
    """A class to generate flight path given a geojson linestring"""

    def __init__(self, config: GeoJSONFlightsSimulatorConfiguration) -> None:
        self.config = config
        self.reference_time = arrow.get(config.reference_time.datetime)
        self.flight_start_shift_time = config.flight_start_shift
        if config.random_seed is None:
            self.random = random
        else:
            self.random = random.Random(x=config.random_seed)

        self.utm_zone = config.utm_zone

        self.altitude_agl = 50.0

        self.flight: FullFlightRecord | None = None

        self.geod = Geod(ellps="WGS84")
        self.flight_path_points: list[Point] = []
        self.center_point: Point | None = None
        self.bounds: tuple[float, float, float, float] | None = None

        # This object holds the name and the polygon object of the query boxes. The number of bboxes are controlled by the `box_diagonals` variable
        self.query_bboxes: List[QueryBoundingBox] = []

        self.flights: List[FullFlightRecord] = []
        self.bbox_center: List[shapely.geometry.Point] = []
        self.box: shapely.geometry.box
        self.half_box: shapely.geometry.box
        self.geod = Geod(ellps="WGS84")

        self.validate_generate_flight_path_points()

    def validate_generate_flight_path_points(self) -> bool:
        """A method to validate the input geojson file and extract the bounding box"""
        geojson_data = self.config.geojson
        if not isinstance(geojson_data, dict):
            raise RuntimeError("Invalid geojson data, not a dictionary")

        if "features" not in geojson_data:
            raise RuntimeError("Invalid geojson data, no features found")

        if len(geojson_data["features"]) == 0:
            raise RuntimeError("Invalid geojson data, no features found")

        feature: Feature = geojson_data["features"][0]
        geometry = feature["geometry"]
        # Cast geometry into GeoJSONLineString
        linestring_geometry = GeoJSONLineString(geometry["coordinates"])
        if not isinstance(linestring_geometry, GeoJSONLineString):
            raise RuntimeError("Invalid geojson data, geometry is not a LineString")

        if not linestring_geometry.is_valid:
            raise RuntimeError("Invalid geojson LineString geometry")

        coordinates = geometry["coordinates"]
        if len(coordinates) < 2:
            raise RuntimeError("Invalid geojson data, LineString must have at least two coordinates")

        self.start_point = GeoJSONPoint(coordinates[0])
        self.end_point = GeoJSONPoint(coordinates[-1])
        self.line_string = LineString(coordinates)
        logger.info(f"Extracted LineString: {self.line_string}")
        # use geod to compute the length of the line string in meters
        line_length = 0
        for i in range(len(coordinates) - 1):
            lon1, lat1 = coordinates[i]
            lon2, lat2 = coordinates[i + 1]
            _, _, distance = self.geod.inv(lon1, lat1, lon2, lat2)
            line_length += distance
        # ensure that the line string is at least 300 meters long
        if line_length < 300:
            raise RuntimeError("Invalid geojson file, LineString must be at least 300 meters long")

        # Use Shapely's LineString for interpolation
        shapely_line = shapely.geometry.LineString(coordinates)
        # Calculate the bounding box of the LineString
        self.box = shapely.geometry.box(*shapely_line.bounds)
        self.half_box = shapely.geometry.box(
            shapely_line.bounds[0],
            shapely_line.bounds[1],
            (shapely_line.bounds[0] + shapely_line.bounds[2]) / 2,
            shapely_line.bounds[3],
        )
        logger.info(f"Bounding box of LineString: {self.box.bounds}")

        num_points = int(line_length / 2)
        distances = (0.004 * i for i in range(num_points))  # speed of 5 meters per second
        logger.info(f"Generating {num_points} flight path points along the LineString")
        for i in distances:
            point = shapely_line.interpolate(i, normalized=True)

            self.flight_path_points.append(Point(point.x, point.y))

        logger.info(f"Generated {len(self.flight_path_points)} flight path points")
        self.center_point = shapely.geometry.Point(
            (self.start_point["coordinates"][0] + self.end_point["coordinates"][0]) / 2,
            (self.start_point["coordinates"][1] + self.end_point["coordinates"][1]) / 2,
        )
        logger.info(f"Center point: {self.center_point}")
        # bounds is in the form (minx, miny, maxx, maxy)
        self.bounds = (
            min(self.start_point["coordinates"][0], self.end_point["coordinates"][0]),
            min(self.start_point["coordinates"][1], self.end_point["coordinates"][1]),
            max(self.start_point["coordinates"][0], self.end_point["coordinates"][0]),
            max(self.start_point["coordinates"][1], self.end_point["coordinates"][1]),
        )
        logger.info(f"Bounds: {self.bounds}")
        return True

    def generate_flight_speed_bearing(self, adjacent_points: List, delta_time_secs: int) -> List[float]:
        """A method to generate flight speed, assume that the flight has to traverse two adjacent points in x number of seconds provided,
        calculating speed in meters / second. It also generates bearing between this and next point,
        this is used to populate the 'track' parameter in the Aircraft State JSON."""

        first_point = adjacent_points[0]
        second_point = adjacent_points[1]

        fwd_azimuth, back_azimuth, adjacent_point_distance_mts = self.geod.inv(first_point.x, first_point.y, second_point.x, second_point.y)

        speed_mts_per_sec = adjacent_point_distance_mts / delta_time_secs
        speed_mts_per_sec = float("{:.2f}".format(speed_mts_per_sec))

        if fwd_azimuth < 0:
            fwd_azimuth = 360 + fwd_azimuth

        return [speed_mts_per_sec, fwd_azimuth]

    def utm_converter(self, shapely_shape: shapely.geometry, inverse: bool = False) -> shapely.geometry.shape:
        """A helper function to convert from lat / lon to UTM coordinates for buffering. tracks. This is the UTM projection (https://en.wikipedia.org/wiki/Universal_Transverse_Mercator_coordinate_system), we use Zone 33T which encompasses Switzerland, this zone has to be set for each locale / city. Adapted from https://gis.stackexchange.com/questions/325926/buffering-geometry-with-points-in-wgs84-using-shapely"""

        proj = Proj(proj="utm", zone=self.utm_zone, ellps="WGS84", datum="WGS84")

        geo_interface = shapely_shape.__geo_interface__
        point_or_polygon = geo_interface["type"]
        coordinates = geo_interface["coordinates"]
        if point_or_polygon == "Polygon":
            new_coordinates = [[proj(*point, inverse=inverse) for point in linring] for linring in coordinates]
        elif point_or_polygon == "Point":
            new_coordinates = proj(*coordinates, inverse=inverse)
        elif point_or_polygon == "LineString":
            new_coordinates = [proj(*point, inverse=inverse) for point in coordinates]
        else:
            raise RuntimeError("Unexpected geo_interface type: {}".format(point_or_polygon))

        return shapely.geometry.shape({"type": point_or_polygon, "coordinates": tuple(new_coordinates)})

    def generate_flight_grid_and_path_points(self, altitude_of_ground_level_wgs_84: float):
        flight_points_with_altitude: List[FlightPoint] = []
        logger.info(f"Generating flight grid and path points at altitude {altitude_of_ground_level_wgs_84} meters")
        all_grid_cell_tracks = []
        for coord in range(0, len(self.flight_path_points) - 1):
            cur_coord = coord
            next_coord = coord + 1
            next_coord = 0 if next_coord == len(self.flight_path_points) else next_coord
            adjacent_points = [
                Point(
                    self.flight_path_points[cur_coord].x,
                    self.flight_path_points[cur_coord].y,
                ),
                Point(
                    self.flight_path_points[next_coord].x,
                    self.flight_path_points[next_coord].y,
                ),
            ]
            flight_speed, bearing = self.generate_flight_speed_bearing(adjacent_points=adjacent_points, delta_time_secs=1)

            flight_points_with_altitude.append(
                FlightPoint(
                    lat=self.flight_path_points[cur_coord].y,
                    lng=self.flight_path_points[cur_coord].x,
                    alt=altitude_of_ground_level_wgs_84,
                    speed=flight_speed,
                    bearing=bearing,
                )
            )
        bounds_box = shapely.geometry.box(*self.bounds)

        all_grid_cell_tracks.append(GridCellFlight(bounds=bounds_box, track=flight_points_with_altitude))

        self.grid_cells_flight_tracks = all_grid_cell_tracks

    def generate_flight_details(self, id: str) -> RIDFlightDetails:
        """This class generates details of flights and operator details for a flight, this data is required for identifying flight, operator and operation"""

        my_flight_details_generator = OperatorFlightDataGenerator(self.random)

        operator_location = my_flight_details_generator.generate_operator_location(centroid=self.center_point)

        # TODO: Put operator_location in center of circle rather than stacking operators of all flights on top of each other
        return RIDFlightDetails(
            id=id,
            serial_number=my_flight_details_generator.generate_serial_number(),
            operation_description=my_flight_details_generator.generate_operation_description(),
            operator_location=operator_location,
            operator_id=my_flight_details_generator.generate_operator_id(),
            registration_number=my_flight_details_generator.generate_registration_number(),
        )

    def generate_rid_state(self, duration):
        """

        This method generates rid_state objects that can be submitted as flight telemetry


        """
        all_flight_telemetry: List[List[RIDAircraftState]] = []
        flight_track_details = {}  # Develop a index of flight length and their index
        # Store where on the track the current index is, since the tracks are circular, once the end of the track is reached, the index is reset to 0 to indicate beginning of the track again.
        flight_current_index = {}
        # Get the number of flights
        num_flights = len(self.grid_cells_flight_tracks)
        logger.info(f"Number of flights: {num_flights}")
        time_increment_seconds = 1  # the number of seconds it takes to go from one point to next on the track
        now = self.reference_time
        now_isoformat = now.isoformat()
        for i in range(num_flights):
            flight_positions_len = len(self.grid_cells_flight_tracks[i].track)

            # in a circular flight pattern increment direction
            angle_increment = 360 / flight_positions_len

            # the resolution of track is 1 degree minimum
            angle_increment = 1.0 if angle_increment == 0.0 else angle_increment

            if i not in flight_track_details:
                flight_track_details[i] = {}
            flight_track_details[i]["track_length"] = flight_positions_len
            flight_current_index[i] = 0
            all_flight_telemetry.append([])

        timestamp = now
        for j in range(duration):
            timestamp = timestamp.shift(seconds=time_increment_seconds)

            for k in range(num_flights):
                timestamp_isoformat = timestamp.shift(seconds=k * self.flight_start_shift_time).isoformat()
                list_end = flight_track_details[k]["track_length"] - flight_current_index[k]

                if list_end != 1:
                    flight_point = self.grid_cells_flight_tracks[k].track[flight_current_index[k]]
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

                    flight_current_index[k] += 1
                else:
                    flight_current_index[k] = 0

        flights = []
        for m in range(num_flights):
            flight = FullFlightRecord(
                reference_time=now_isoformat,
                states=all_flight_telemetry[m],
                flight_details=self.generate_flight_details(id=str(m)),
                aircraft_type="Helicopter",
            )
            flights.append(flight)
        self.flights = flights


def generate_aircraft_states(
    config: GeoJSONFlightsSimulatorConfiguration,
) -> FlightRecordCollection:
    my_path_generator = GeoJSONFlightsSimulator(config)

    my_path_generator.generate_flight_grid_and_path_points(altitude_of_ground_level_wgs_84=config.altitude_of_ground_level_wgs_84)

    my_path_generator.generate_rid_state(duration=30)
    flights = my_path_generator.flights

    result = FlightRecordCollection(flights=flights)

    # Fix type errors (TODO: fix these at the source rather than here)
    return ImplicitDict.parse(result, FlightRecordCollection)


if __name__ == "__main__":
    # Load configuration from config.json
    MAX_ALTITUDEE_WGS84 = 150
    MIN_ALTITUDE_WGS84 = 100

    config_file_path = "config.json"

    print(f"Loading configuration from: {config_file_path}")
    if os.path.exists(config_file_path):
        with open(config_file_path, "r", encoding="utf-8") as config_file:
            config_data = json.load(config_file)

    else:
        logger.warning(f"Config file not found. Using default values.")
        sys.exit("Execution stopped: Config file not found.")
    geojson_data = config_data["linear_geojson"]
    my_flight_generator = GeoJSONFlightsSimulator(
        config=GeoJSONFlightsSimulatorConfiguration(
            reference_time=arrow.utcnow(),
            geojson=geojson_data,
            altitude_of_ground_level_wgs_84=200,
            random_seed=None,
        )
    )
    my_flight_generator.generate_flight_grid_and_path_points(altitude_of_ground_level_wgs_84=500)

    my_flight_generator.generate_rid_state(duration=30)
    # Add the bounding box as GeoJSON to the flight declaration
    # Create the output directory if it does not exist
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Output directory created or already exists: {output_dir}")

    bbox_file = os.path.join(output_dir, "flight_declaration_bounding_box.json")
    half_box_bbox_file = os.path.join(output_dir, "flight_declaration_half_bounding_box.json")
    flight_data_file = os.path.join(output_dir, "flight_data.json")

    half_bbox_geojson = shapely.geometry.mapping(my_flight_generator.half_box)
    bbox_geojson = shapely.geometry.mapping(my_flight_generator.box)

    logger.info("Generated GeoJSON for bounding boxes.")

    logger.info(f"Number of flights generated: {len(my_flight_generator.flights)}")
    all_flights = []
    for flight in my_flight_generator.flights:
        all_flights.append(json.loads(json.dumps(flight)))
        break
    with open(flight_data_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(all_flights))
    logger.info(f"Flight data saved to: {flight_data_file}")
