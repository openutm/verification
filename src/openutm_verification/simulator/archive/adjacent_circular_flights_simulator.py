import json
import logging
import os
import random
from datetime import timedelta
from typing import List

import arrow
import shapely.geometry
from geojson import Feature, FeatureCollection
from geojson import Polygon as GeoJSONPolygon
from implicitdict import ImplicitDict
from pyproj import Geod, Proj, Transformer
from shapely.geometry import Point, Polygon
from uas_standards.astm.f3411.v22a.api import (
    HorizontalAccuracy,
    RIDAircraftPosition,
    RIDAircraftState,
    RIDFlightDetails,
    RIDHeight,
    Time,
    VerticalAccuracy,
)

from openutm_verification.simulator.flight_data import (
    AdjacentCircularFlightsSimulatorConfiguration,
    FlightRecordCollection,
    FullFlightRecord,
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


class AdjacentCircularFlightsSimulator:
    """A class to generate Flight Paths given a bounding box, this is the main module to generate flight path datasets,
    the data is generated as latitude / longitude pairs with associated with the flights.
    Additional flight metadata e.g. flight id, altitude, registration number can also be generated
    """

    def __init__(self, config: AdjacentCircularFlightsSimulatorConfiguration) -> None:
        """Create an AdjacentCircularFlightsSimulator with the specified bounding box.

        Once these extents are specified, a grid will be created with two rows.  The idea is that multiple flights tracks will be created within the extents.

        Raises:
        ValueError: If bounding box has more area than a 500m x 500m square.
        """
        self.reference_time = arrow.get(config.reference_time.datetime)
        self.flight_start_shift_time = config.flight_start_shift
        if config.random_seed is None:
            self.random = random
        else:
            self.random = random.Random(x=config.random_seed)
        self.minx = config.minx
        self.miny = config.miny
        self.maxx = config.maxx
        self.maxy = config.maxy
        self.utm_zone = config.utm_zone

        self.altitude_agl = 50.0

        self.grid_cells_flight_tracks: List[GridCellFlight] = []

        # This object holds the name and the polygon object of the query boxes. The number of bboxes are controlled by the `box_diagonals` variable
        self.query_bboxes: List[QueryBoundingBox] = []

        self.flights: List[FullFlightRecord] = []
        self.bbox_center: List[shapely.geometry.Point] = []
        self.box: shapely.geometry.box
        self.half_box: shapely.geometry.box
        self.geod = Geod(ellps="WGS84")

        self.input_extents_valid()

    def input_extents_valid(self) -> None:
        """
        Validates and adjusts the input bounding box extents to ensure the area matches a target value.
        This method recalculates the bounding box defined by `minx`, `miny`, `maxx`, and `maxy` so that its area
        is scaled to a target area (default: 250,000 m², equivalent to 500m x 500m). The box is scaled about its center,
        and the new bounds are updated accordingly. The method logs the scale factor, new bounds, new area, and the
        diagonal length of the adjusted box.
        Side Effects:
            - Updates `self.minx`, `self.miny`, `self.maxx`, `self.maxy` to new scaled values.
            - Updates `self.box` with the new bounding box geometry.
            - Logs relevant information about the scaling process.
        Returns:
            None
        """

        box = shapely.geometry.box(self.minx, self.miny, self.maxx, self.maxy)
        self.box = box
        area = abs(self.geod.geometry_area_perimeter(box)[0])
        target_area = 250000  # 500m x 500m
        scale_factor = (target_area / area) ** 0.5
        logger.info(f"Scale factor: {scale_factor}")
        center_x = (self.minx + self.maxx) / 2
        center_y = (self.miny + self.maxy) / 2
        width = (self.maxx - self.minx) * scale_factor
        height = (self.maxy - self.miny) * scale_factor
        self.minx = center_x - width / 2
        self.maxx = center_x + width / 2
        self.miny = center_y - height / 2
        self.maxy = center_y + height / 2
        # Generate a half-sized bounding box centered at the same location
        half_width = width / 2
        half_height = height / 2
        half_minx = center_x - half_width / 2
        half_maxx = center_x + half_width / 2
        half_miny = center_y - half_height / 2
        half_maxy = center_y + half_height / 2
        self.half_box = shapely.geometry.box(half_minx, half_miny, half_maxx, half_maxy)
        logger.info(f"New bounds: minx: {self.minx}, miny: {self.miny}, maxx: {self.maxx}, maxy: {self.maxy}")
        box = shapely.geometry.box(self.minx, self.miny, self.maxx, self.maxy)
        area = abs(self.geod.geometry_area_perimeter(box)[0])
        logger.info(f"New area: {area} m²")
        diagonal_length = self.geod.inv(self.minx, self.miny, self.maxx, self.maxy)[2]
        logger.info(f"New diagonal length: {diagonal_length} meters")

    def generate_query_bboxes(self):
        """For the different Remote ID checks: No, we need to generate three bounding boxes for the display provider, this method generates the 1 km diagonal length bounding box"""
        # Get center of of the bounding box that is inputted into the generator
        box = shapely.geometry.box(self.minx, self.miny, self.maxx, self.maxy)
        center = box.centroid
        self.bbox_center.append(center)
        # Transform to geographic coordinates to get areas
        transformer = Transformer.from_crs("epsg:4326", "epsg:3857")
        transformed_x, transformed_y = transformer.transform(center.x, center.y)
        pt = Point(transformed_x, transformed_y)
        # Now we have a point, we can buffer the point and create bounding boxes of the buffer to get the appropriate polygons, more than three boxes can be created, for the tests three will suffice.
        now = self.reference_time

        box_diagonals = [
            {
                "length": 150,
                "name": "zoomed_in_detail",
                "timestamp_after": now + timedelta(seconds=60),
                "timestamp_before": now + timedelta(seconds=90),
            },
            {
                "length": 380,
                "name": "whole_flight_area",
                "timestamp_after": now + timedelta(seconds=30),
                "timestamp_before": now + timedelta(seconds=60),
            },
            {
                "length": 3000,
                "name": "too_large_query",
                "timestamp_after": now + timedelta(seconds=10),
                "timestamp_before": now + timedelta(seconds=30),
            },
        ]

        for box_id, box_diagonal in enumerate(box_diagonals):
            # Buffer the point with the appropriate length
            buffer = pt.buffer(box_diagonal["length"])
            buffer_bounds = buffer.bounds
            buffer_bounds_polygon = shapely.geometry.box(buffer_bounds[0], buffer_bounds[1], buffer_bounds[2], buffer_bounds[3])
            buffer_points = zip(
                buffer_bounds_polygon.exterior.coords.xy[0],
                buffer_bounds_polygon.exterior.coords.xy[1],
            )
            proj_buffer_points = []
            # reproject back to ESPG 4326
            transformer2 = Transformer.from_crs("epsg:3857", "epsg:4326")
            for point in buffer_points:
                x = point[0]
                y = point[1]
                x, y = transformer2.transform(x, y)
                proj_buffer_points.append((x, y))

            buffered_box = Polygon(proj_buffer_points)
            # Get the bounds of the buffered box, this is the one that will will be fed to the remote ID display provider to query
            self.query_bboxes.append(
                QueryBoundingBox(
                    name=box_diagonals[box_id]["name"],
                    shape=buffered_box,
                    timestamp_after=box_diagonals[box_id]["timestamp_after"].datetime,
                    timestamp_before=box_diagonals[box_id]["timestamp_before"].datetime,
                )
            )

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
        else:
            raise RuntimeError("Unexpected geo_interface type: {}".format(point_or_polygon))

        return shapely.geometry.shape({"type": point_or_polygon, "coordinates": tuple(new_coordinates)})

    def generate_flight_grid_and_path_points(self, altitude_of_ground_level_wgs_84: float):
        """Generate a series of boxes (grid) within the given bounding box to have areas for different flight tracks within each box"""
        # Compute the box where the flights will be created. For a the sample bounds given, over Bern, Switzerland,
        # a division by 2 produces a cell_size of 0.0025212764739985793, a division of 3 is 0.0016808509826657196 and division by 4 0.0012606382369992897.
        # As the cell size goes smaller more number of flights can be accommodated within the grid. For the study area bounds we build a 3x2 box
        # for six flights by creating 3 column 2 row grid.
        N_COLS = 3
        N_ROWS = 2
        cell_size_x = (self.maxx - self.minx) / (N_COLS)  # create three columns
        cell_size_y = (self.maxy - self.miny) / (N_ROWS)  # create two rows
        grid_cells = []
        for u0 in range(0, N_COLS):  # 3 columns
            x0 = self.minx + (u0 * cell_size_x)
            for v0 in range(0, N_ROWS):  # 2 rows
                y0 = self.miny + (v0 * cell_size_y)
                x1 = x0 + cell_size_x
                y1 = y0 + cell_size_y
                grid_cells.append(shapely.geometry.box(x0, y0, x1, y1))

        all_grid_cell_tracks = []
        """ For each of the boxes (grid) allocated to the operator, get the centroid and buffer to generate a flight path. A 50 m radius is provided to have flight paths within each of the boxes """
        # Iterate over the flight_grid
        for grid_cell in grid_cells:
            center = grid_cell.centroid
            center_utm = self.utm_converter(center)
            buffer_shape_utm = center_utm.buffer(50)
            buffered_path = self.utm_converter(buffer_shape_utm, inverse=True)
            altitude = altitude_of_ground_level_wgs_84 + self.altitude_agl  # meters WGS 84
            flight_points_with_altitude = []
            x, y = buffered_path.exterior.coords.xy

            for coord in range(0, len(x)):
                cur_coord = coord
                next_coord = coord + 1
                next_coord = 0 if next_coord == len(x) else next_coord
                adjacent_points = [
                    Point(x[cur_coord], y[cur_coord]),
                    Point(x[next_coord], y[next_coord]),
                ]
                flight_speed, bearing = self.generate_flight_speed_bearing(adjacent_points=adjacent_points, delta_time_secs=1)

                flight_points_with_altitude.append(
                    FlightPoint(
                        lat=y[coord],
                        lng=x[coord],
                        alt=altitude,
                        speed=flight_speed,
                        bearing=bearing,
                    )
                )

            all_grid_cell_tracks.append(GridCellFlight(bounds=grid_cell, track=flight_points_with_altitude))

        self.grid_cells_flight_tracks = all_grid_cell_tracks

    def generate_flight_details(self, id: str) -> RIDFlightDetails:
        """This class generates details of flights and operator details for a flight, this data is required for identifying flight, operator and operation"""

        my_flight_details_generator = OperatorFlightDataGenerator(self.random)

        # TODO: Put operator_location in center of circle rather than stacking operators of all flights on top of each other
        return RIDFlightDetails(
            id=id,
            serial_number=my_flight_details_generator.generate_serial_number(),
            operation_description=my_flight_details_generator.generate_operation_description(),
            operator_location=my_flight_details_generator.generate_operator_location(centroid=self.bbox_center[0]),
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
    config: AdjacentCircularFlightsSimulatorConfiguration,
) -> FlightRecordCollection:
    my_path_generator = AdjacentCircularFlightsSimulator(config)

    my_path_generator.generate_flight_grid_and_path_points(altitude_of_ground_level_wgs_84=config.altitude_of_ground_level_wgs_84)
    my_path_generator.generate_query_bboxes()

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
            minx = config_data.get("minx", 7.4719589491516558)
            miny = config_data.get("miny", 46.9799127188803993)
            maxx = config_data.get("maxx", 7.4870457729811619)
            maxy = config_data.get("maxy", 46.9865389634242945)
    else:
        logger.warning(f"Config file not found. Using default values.")
        minx = 7.4719589491516558
        miny = 46.9799127188803993
        maxx = 7.4870457729811619
        maxy = 46.9865389634242945
    my_flight_generator = AdjacentCircularFlightsSimulator(
        config=AdjacentCircularFlightsSimulatorConfiguration(
            reference_time=arrow.utcnow(),
            minx=minx,
            miny=miny,
            maxx=maxx,
            maxy=maxy,
            altitude_of_ground_level_wgs_84=200,
            random_seed=None,
        )
    )
    my_flight_generator.generate_flight_grid_and_path_points(altitude_of_ground_level_wgs_84=500)
    my_flight_generator.generate_query_bboxes()
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

    # Read the flight declaration template
    template_file = os.path.join("templates", "flight_declaration_template.json")
    logger.info(f"Reading flight declaration template from: {template_file}")

    with open(template_file, "r", encoding="utf-8") as template:
        flight_declaration_geojson = json.load(template)

    logger.info("Flight declaration template loaded successfully.")

    # Update the start and end datetime
    flight_declaration_geojson["start_datetime"] = my_flight_generator.reference_time.datetime.isoformat()
    flight_declaration_geojson["end_datetime"] = my_flight_generator.reference_time.shift(minutes=10).datetime.isoformat()

    bbox_polygon = GeoJSONPolygon(coordinates=bbox_geojson["coordinates"])
    bbox_geojson_feature = Feature(
        geometry=bbox_polygon,
        properties={
            "max_altitude": {"meters": MAX_ALTITUDEE_WGS84, "datum": "WGS84"},
            "min_altitude": {"meters": MIN_ALTITUDE_WGS84, "datum": "WGS84"},
        },
    )
    bbox_geojson_feature_collection = FeatureCollection(features=[bbox_geojson_feature])
    # Update the GeoJSON with the bounding box
    flight_declaration_geojson["flight_declaration_geo_json"] = bbox_geojson_feature_collection.__geo_interface__

    halfbox_bbox_polygon = GeoJSONPolygon(coordinates=half_bbox_geojson["coordinates"])
    halfbox_bbox_geojson_feature = Feature(
        geometry=halfbox_bbox_polygon,
        properties={
            "max_altitude": {"meters": MAX_ALTITUDEE_WGS84, "datum": "WGS84"},
            "min_altitude": {"meters": MIN_ALTITUDE_WGS84, "datum": "WGS84"},
        },
    )
    halfbox_bbox_geojson_feature_collection = FeatureCollection(features=[halfbox_bbox_geojson_feature])

    half_box_flight_declaration = flight_declaration_geojson.copy()
    half_box_flight_declaration["flight_declaration_geo_json"] = halfbox_bbox_geojson_feature_collection.__geo_interface__

    with open(bbox_file, "w", encoding="utf-8") as updated_file:
        json.dump(flight_declaration_geojson, updated_file, indent=2)
    logger.info(f"Bounding box GeoJSON saved to: {bbox_file}")

    # Save the updated flight declaration
    with open(half_box_bbox_file, "w", encoding="utf-8") as updated_file:
        json.dump(half_box_flight_declaration, updated_file, indent=2)
    logger.info(f"Half bounding box GeoJSON saved to: {half_box_bbox_file}")

    logger.info(f"Number of flights generated: {len(my_flight_generator.flights)}")
    all_flights = []
    for flight in my_flight_generator.flights:
        all_flights.append(json.loads(json.dumps(flight)))
        break
    with open(flight_data_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(all_flights))
    logger.info(f"Flight data saved to: {flight_data_file}")
