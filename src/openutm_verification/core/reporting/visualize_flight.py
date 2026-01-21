"""
This script visualizes a flight path and its declared geofence from JSON files
onto an interactive map.
It reads flight telemetry data and a flight declaration, extracts the GPS
coordinates and GeoJSON polygon, and uses the Folium library to plot them on an
OpenStreetMap. The resulting map is saved as an HTML file.
Usage:
    - Ensure 'folium', 'pythreejs', 'ipywidgets', and 'numpy' are installed.
    - Run the script from the command line:
        python flight_blender_e2e_integration/visualize_flight.py
    - Open the generated '..._3d.html' file in a web browser for an interactive 3D view.
"""

import json
import math
from pathlib import Path

import folium
import numpy as np
import pythreejs as three
from ipywidgets import embed
from loguru import logger
from uas_standards.astm.f3411.v22a.api import RIDAircraftState

from openutm_verification.simulator.models.flight_data_types import FlightObservationSchema

# Color palette for airplane tracks (orange-based colors for distinction from drone blue)
AIRPLANE_COLORS = ["#FF8C00", "#FF6347", "#FFA500", "#FF4500", "#FFD700", "#FF7F50", "#FF69B4", "#DC143C"]


def visualize_flight_path_2d(
    telemetry_data: list[RIDAircraftState],
    declaration_data: dict,
    output_html_path: Path,
    air_traffic_data: list[list[FlightObservationSchema]] | None = None,
):
    """
    Creates an interactive 2D map from flight telemetry and declaration data.

    Args:
        telemetry_data (dict): The flight telemetry data as a dictionary.
        declaration_data (dict): The flight declaration data as a dictionary.
        output_html_path (Path): The full path where the output HTML map will be saved.
        air_traffic_data (list[list[FlightObservationSchema]] | None): Optional air traffic data from simulators.
    """
    logger.info("Starting 2D flight path visualization")

    states = telemetry_data
    path_points_with_alt = [
        (s["position"]["lat"], s["position"]["lng"], s["position"]["alt"]) for s in states if "position" in s and "alt" in s["position"]
    ]
    coordinates = [(p[0], p[1]) for p in path_points_with_alt]
    geofence = declaration_data.get("flight_declaration_geo_json")

    logger.debug(f"Extracted {len(coordinates)} coordinate points from telemetry data")
    logger.debug(f"Geofence data present: {geofence is not None}")

    if not coordinates and not geofence:
        logger.warning("No coordinates or geofence found in the data.")
        return

    if geofence:
        first_coord = geofence["features"][0]["geometry"]["coordinates"][0][1]
        map_center = [first_coord[1], first_coord[0]]
        logger.debug(f"Using geofence center for map: {map_center}")
    elif coordinates:
        lat, lng = coordinates[0]
        map_center = [lat, lng]
        logger.debug(f"Using first coordinate for map center: {map_center}")
    else:
        map_center = [46.97, 7.47]
        logger.debug(f"Using default map center: {map_center}")

    flight_map = folium.Map(location=map_center, zoom_start=15)
    logger.debug("Initialized Folium map")

    if geofence:
        g = folium.GeoJson(geofence, style_function=lambda x: {"color": "red", "weight": 2, "fillOpacity": 0.1}, tooltip="Declared Geofence")
        if "features" in geofence:
            for feature in geofence.get("features", []):
                geometry = feature.get("geometry")
                if geometry and geometry.get("type") == "Polygon":
                    for i, coord in enumerate(geometry["coordinates"][0][:-1]):
                        lat, lng = coord[1], coord[0]
                        folium.Marker(
                            [lat, lng], popup=f"Corner {i + 1}:<br>Lat={lat}<br>Lng={lng}", icon=folium.Icon(color="purple", icon="info-sign")
                        ).add_to(g)
        g.add_to(flight_map)
        logger.debug("Added geofence to map")

    if coordinates:
        folium.PolyLine(locations=coordinates, color="blue", weight=3, opacity=0.8, tooltip="Flight Path").add_to(flight_map)
        for lat, lng, alt in path_points_with_alt:
            folium.CircleMarker(
                location=(lat, lng),
                radius=2,
                color="blue",
                fill=True,
                fill_color="blue",
                tooltip=f"Altitude: {alt:.2f}m",
            ).add_to(flight_map)
        folium.Marker(
            location=coordinates[0],
            popup=f"Start Point: Lat={coordinates[0][0]}, Lng={coordinates[0][1]}",
            icon=folium.Icon(color="green", icon="play"),
        ).add_to(flight_map)
        folium.Marker(
            location=coordinates[-1],
            popup=f"End Point: Lat={coordinates[-1][0]}, Lng={coordinates[-1][1]}",
            icon=folium.Icon(color="red", icon="stop"),
        ).add_to(flight_map)
        logger.debug("Added flight path and markers to map")

    # Add airplane/air traffic paths if available
    if air_traffic_data:
        _add_air_traffic_to_2d_map(flight_map, air_traffic_data)

    flight_map.save(output_html_path)
    logger.info(f"2D flight path visualization saved to: {output_html_path}")


def _reorganize_air_traffic_by_aircraft(
    air_traffic_data: list[list[FlightObservationSchema]],
) -> dict[str, list]:
    """
    Reorganizes air traffic data from timestamp-based to aircraft-based grouping.

    The input data may be organized as list of timestamps, where each timestamp
    contains observations from multiple aircraft. This function reorganizes it
    into a dict keyed by ICAO address with all observations for that aircraft.

    Args:
        air_traffic_data: Air traffic data (may be organized by timestamp or aircraft).

    Returns:
        Dict mapping ICAO address to list of observations for that aircraft.
    """
    aircraft_tracks: dict[str, list] = {}

    for observations in air_traffic_data:
        for obs in observations:
            # Handle both dict and Pydantic model
            if isinstance(obs, dict):
                icao = obs.get("icao_address", "UNKNOWN")
            else:
                icao = obs.icao_address

            if icao not in aircraft_tracks:
                aircraft_tracks[icao] = []
            aircraft_tracks[icao].append(obs)

    return aircraft_tracks


def _add_air_traffic_to_2d_map(
    flight_map: folium.Map,
    air_traffic_data: list[list[FlightObservationSchema]],
) -> None:
    """
    Adds airplane/air traffic paths to the 2D map with distinct colors.

    Args:
        flight_map: The Folium map to add paths to.
        air_traffic_data: Air traffic data as list of aircraft, each with list of observations.
    """
    # Reorganize data by aircraft ICAO address
    aircraft_tracks = _reorganize_air_traffic_by_aircraft(air_traffic_data)
    logger.debug(f"Adding {len(aircraft_tracks)} airplane tracks to 2D map")

    for idx, (icao_address, aircraft_observations) in enumerate(sorted(aircraft_tracks.items())):
        if not aircraft_observations:
            continue

        # Get color from palette (cycle if more aircraft than colors)
        color = AIRPLANE_COLORS[idx % len(AIRPLANE_COLORS)]

        # Extract path coordinates - handle both dict and Pydantic model
        path_points_with_alt = []
        for obs in aircraft_observations:
            if isinstance(obs, dict):
                lat = obs.get("lat_dd")
                lon = obs.get("lon_dd")
                alt = obs.get("altitude_mm", 0) / 1000  # Convert mm to meters
            else:
                lat = obs.lat_dd
                lon = obs.lon_dd
                alt = obs.altitude_mm / 1000  # Convert mm to meters
            if lat is not None and lon is not None:
                path_points_with_alt.append((lat, lon, alt))

        if not path_points_with_alt:
            continue

        coordinates = [(p[0], p[1]) for p in path_points_with_alt]

        # Draw the airplane path (icao_address already from loop)
        folium.PolyLine(
            locations=coordinates,
            color=color,
            weight=4,
            opacity=0.9,
            dash_array="10, 5",  # Dashed line to distinguish from drone
            tooltip=f"Airplane {icao_address}",
        ).add_to(flight_map)

        # Add small markers along the path for all data points
        for lat, lon, alt in path_points_with_alt:
            folium.CircleMarker(
                location=(lat, lon),
                radius=3,
                color=color,
                fill=True,
                fill_color=color,
                tooltip=f"Airplane {icao_address}: Alt={alt:.0f}m",
            ).add_to(flight_map)

        # Map hex colors to folium color names for markers
        marker_color_map = {
            "#FF8C00": "orange",
            "#FF6347": "red",
            "#FFA500": "beige",
            "#FF4500": "darkred",
            "#FFD700": "lightgreen",
            "#FF7F50": "pink",
            "#FF69B4": "purple",
            "#DC143C": "cadetblue",
        }
        marker_color = marker_color_map.get(color, "orange")

        # Add start marker for airplane
        folium.Marker(
            location=coordinates[0],
            popup=f"Airplane {icao_address} Start<br>Lat={coordinates[0][0]:.6f}<br>Lng={coordinates[0][1]:.6f}",
            icon=folium.Icon(color=marker_color, icon="plane", prefix="fa"),
        ).add_to(flight_map)

        # Add end marker for airplane
        if len(coordinates) > 1:
            folium.Marker(
                location=coordinates[-1],
                popup=f"Airplane {icao_address} End<br>Lat={coordinates[-1][0]:.6f}<br>Lng={coordinates[-1][1]:.6f}",
                icon=folium.Icon(color="black", icon="plane", prefix="fa"),
            ).add_to(flight_map)

        logger.debug(f"Added airplane track for {icao_address} with {len(coordinates)} points")


# ==============================================================================
# 3D Visualization (pythreejs) - Refactored into Helper Functions
# ==============================================================================


def _setup_3d_scene():
    """Initializes and configures the three.js scene, camera, and lighting."""
    # Set a default camera position; it will be overridden by auto-framing logic.
    camera = three.PerspectiveCamera(position=[0, 500, 1500], fov=50, aspect=1000 / 800)
    scene = three.Scene(background="lightgray")
    scene.add(three.AmbientLight(color="#cccccc"))
    scene.add(three.DirectionalLight(color="white", position=[0, 1, 1], intensity=0.6))
    scene.add(three.AxesHelper(200))
    scene.add(three.GridHelper(size=3000, divisions=20, colorCenterLine="gray", colorGrid="darkgray"))
    return camera, scene


def _create_flight_path_group(projected_path):
    """Creates a three.js group containing the flight path and markers."""
    if not projected_path:
        return None
    path_group = three.Group()
    path_geometry = three.BufferGeometry(attributes={"position": three.BufferAttribute(np.array(projected_path, dtype="float32"))})
    path_material = three.LineBasicMaterial(color="blue", linewidth=3)
    path_group.add(three.Line(path_geometry, path_material))

    # Add small dots for each coordinate
    points_material = three.PointsMaterial(color="blue", size=3, sizeAttenuation=False)
    path_group.add(three.Points(path_geometry, points_material))
    start_marker = three.Mesh(three.SphereBufferGeometry(15), three.MeshBasicMaterial(color="green"))
    start_marker.position = projected_path[0]
    path_group.add(start_marker)
    end_marker = three.Mesh(three.SphereBufferGeometry(15), three.MeshBasicMaterial(color="red"))
    end_marker.position = projected_path[-1]
    path_group.add(end_marker)
    return path_group


def _create_geofence_box_group(projected_geofence_corners_2d, min_alt, max_alt):
    """Creates a three.js group for the geofence box (wireframe and faces)."""
    if not projected_geofence_corners_2d:
        return None

    bottom_verts = [[x, min_alt, z] for x, z in projected_geofence_corners_2d]
    top_verts = [[x, max_alt, z] for x, z in projected_geofence_corners_2d]
    geofence_group = three.Group()

    line_mat = three.LineBasicMaterial(color="red", linewidth=2)
    geofence_group.add(
        three.Line(
            three.BufferGeometry(attributes={"position": three.BufferAttribute(np.array(bottom_verts + [bottom_verts[0]], dtype="float32"))}),
            line_mat,
        )
    )
    geofence_group.add(
        three.Line(
            three.BufferGeometry(attributes={"position": three.BufferAttribute(np.array(top_verts + [top_verts[0]], dtype="float32"))}), line_mat
        )
    )
    for bv, tv in zip(bottom_verts, top_verts):
        geofence_group.add(
            three.Line(three.BufferGeometry(attributes={"position": three.BufferAttribute(np.array([bv, tv], dtype="float32"))}), line_mat)
        )

    side_face_mat = three.MeshBasicMaterial(color="red", side="DoubleSide", opacity=0.1, transparent=True)
    floor_mat = three.MeshBasicMaterial(color="green", side="DoubleSide", opacity=0.2, transparent=True)
    ceiling_mat = three.MeshBasicMaterial(color="blue", side="DoubleSide", opacity=0.2, transparent=True)

    for i in range(len(bottom_verts)):
        p1_b, p2_b = bottom_verts[i], bottom_verts[(i + 1) % len(bottom_verts)]
        p1_t, p2_t = top_verts[i], top_verts[(i + 1) % len(top_verts)]
        face_verts = np.array([p1_b, p2_b, p1_t, p2_b, p2_t, p1_t], dtype="float32")
        face_geom = three.BufferGeometry(attributes={"position": three.BufferAttribute(face_verts)})
        geofence_group.add(three.Mesh(face_geom, side_face_mat))

    def create_cap_mesh(vertices_2d_xz, altitude, material):
        """Creates a cap mesh (floor or ceiling) on the XZ plane at a given altitude (y)."""
        if len(vertices_2d_xz) < 3:
            return None
        # pythreejs Shape works in 2D (x, y). We provide our (x, z) coordinates.
        shape = three.Shape(points=vertices_2d_xz)
        geom = three.ShapeGeometry(shapes=[shape])
        mesh = three.Mesh(geom, material)
        # The shape is created on the XY plane. We need to rotate it to the XZ plane.
        mesh.rotation = [-math.pi / 2, 0, 0, "XYZ"]
        # Then, we position it at the correct altitude (y-coordinate).
        # mesh.position.y = altitude
        return mesh

    if floor_mesh := create_cap_mesh(projected_geofence_corners_2d, min_alt, floor_mat):
        geofence_group.add(floor_mesh)
    if ceiling_mesh := create_cap_mesh(projected_geofence_corners_2d, max_alt, ceiling_mat):
        geofence_group.add(ceiling_mesh)

    return geofence_group


# Color palette for airplane tracks in 3D (hex colors for pythreejs)
AIRPLANE_COLORS_3D = ["#FF8C00", "#FF6347", "#FFA500", "#FF4500", "#FFD700", "#FF7F50", "#FF69B4", "#DC143C"]


def _create_airplane_path_group(projected_path: list[tuple[float, float, float]], color: str) -> three.Group | None:
    """Creates a three.js group containing an airplane flight path with distinct color.

    Args:
        projected_path: List of (x, y, z) projected coordinates.
        color: Hex color string for the path.

    Returns:
        three.Group containing the airplane path visualization, or None if no path.
    """
    if not projected_path:
        return None

    path_group = three.Group()

    # Create the line path
    path_geometry = three.BufferGeometry(attributes={"position": three.BufferAttribute(np.array(projected_path, dtype="float32"))})
    path_material = three.LineBasicMaterial(color=color, linewidth=2)
    path_group.add(three.Line(path_geometry, path_material))

    # Add small dots for each coordinate
    points_material = three.PointsMaterial(color=color, size=2, sizeAttenuation=False)
    path_group.add(three.Points(path_geometry, points_material))

    # Add start marker (small sphere)
    start_marker = three.Mesh(three.SphereBufferGeometry(10), three.MeshBasicMaterial(color=color))
    start_marker.position = projected_path[0]
    path_group.add(start_marker)

    # Add end marker (slightly larger sphere)
    if len(projected_path) > 1:
        end_marker = three.Mesh(three.SphereBufferGeometry(12), three.MeshBasicMaterial(color="#8B0000"))  # Dark red
        end_marker.position = projected_path[-1]
        path_group.add(end_marker)

    return path_group


def _add_air_traffic_to_3d_scene(
    scene: three.Scene,
    air_traffic_data: list[list[FlightObservationSchema]],
    project_fn,
) -> list[tuple[float, float, float]]:
    """
    Adds airplane/air traffic paths to the 3D scene with distinct colors.

    Args:
        scene: The pythreejs Scene to add paths to.
        air_traffic_data: Air traffic data as list of aircraft, each with list of observations.
        project_fn: Projection function (lon, lat, alt) -> (x, y, z).

    Returns:
        List of all projected points added to the scene (useful for auto-framing if needed).
    """
    all_plane_points = []
    # Reorganize data by aircraft ICAO address
    aircraft_tracks = _reorganize_air_traffic_by_aircraft(air_traffic_data)
    logger.debug(f"Adding {len(aircraft_tracks)} airplane tracks to 3D scene")

    for idx, (icao_address, aircraft_observations) in enumerate(sorted(aircraft_tracks.items())):
        if not aircraft_observations:
            continue

        # Get color from palette (cycle if more aircraft than colors)
        color = AIRPLANE_COLORS_3D[idx % len(AIRPLANE_COLORS_3D)]

        # Extract and project path coordinates - handle both dict and Pydantic model
        projected_airplane_path = []
        for obs in aircraft_observations:
            if isinstance(obs, dict):
                lon = obs.get("lon_dd")
                lat = obs.get("lat_dd")
                alt = obs.get("altitude_mm", 0) / 1000  # Convert mm to meters
            else:
                lon = obs.lon_dd
                lat = obs.lat_dd
                alt = obs.altitude_mm / 1000  # Convert mm to meters

            if lat is not None and lon is not None:
                projected_point = project_fn(lon, lat, alt)
                projected_airplane_path.append(projected_point)
                all_plane_points.append(projected_point)

        if not projected_airplane_path:
            continue

        # Create and add the airplane path group (icao_address already from loop)
        if airplane_group := _create_airplane_path_group(projected_airplane_path, color):
            scene.add(airplane_group)
            logger.debug(f"Added airplane track for {icao_address} with {len(projected_airplane_path)} points")

    return all_plane_points


def visualize_flight_path_3d(
    telemetry_data: list[RIDAircraftState],
    declaration_data: dict,
    output_html_path: Path,
    air_traffic_data: list[list[FlightObservationSchema]] | None = None,
):
    """Creates an interactive 3D visualization of the flight path and geofence.

    Args:
        telemetry_data: The flight telemetry data as a list of RID aircraft states.
        declaration_data: The flight declaration data as a dictionary.
        output_html_path: The full path where the output HTML will be saved.
        air_traffic_data: Optional air traffic data from simulators.
    """
    logger.info("Starting 3D flight path visualization")

    states = telemetry_data
    path_coords_ll = [[s["position"]["lng"], s["position"]["lat"], s["position"]["alt"]] for s in states if "position" in s]
    geofence = declaration_data.get("flight_declaration_geo_json")
    geofence_coords_ll, min_alt, max_alt = [], 0, 0
    if geofence and geofence.get("features"):
        feature = geofence["features"][0]
        geofence_coords_ll = feature["geometry"]["coordinates"][0][:-1]
        min_alt = feature["properties"]["min_altitude"]["meters"]
        max_alt = feature["properties"]["max_altitude"]["meters"]
        logger.debug(f"Extracted geofence with {len(geofence_coords_ll)} corners, min_alt={min_alt}, max_alt={max_alt}")

    logger.debug(f"Extracted {len(path_coords_ll)} path coordinates from telemetry data")

    # Check if we have any data to visualize (including air traffic)
    has_drone_data = bool(path_coords_ll) or bool(geofence_coords_ll)
    has_air_traffic = bool(air_traffic_data)

    if not has_drone_data and not has_air_traffic:
        logger.warning("No data to visualize in 3D.")
        return

    # Calculate center from available data
    all_lons = [p[0] for p in path_coords_ll] + [p[0] for p in geofence_coords_ll]
    all_lats = [p[1] for p in path_coords_ll] + [p[1] for p in geofence_coords_ll]

    # If we only have air traffic data, get center from that
    if not all_lons and air_traffic_data:
        aircraft_tracks = _reorganize_air_traffic_by_aircraft(air_traffic_data)
        for observations in aircraft_tracks.values():
            for obs in observations:
                if isinstance(obs, dict):
                    lon, lat = obs.get("lon_dd"), obs.get("lat_dd")
                else:
                    lon, lat = obs.lon_dd, obs.lat_dd
                if lon is not None and lat is not None:
                    all_lons.append(lon)
                    all_lats.append(lat)

    if not all_lons:
        logger.warning("No longitude data available for centering.")
        return
    center_lon, center_lat = sum(all_lons) / len(all_lons), sum(all_lats) / len(all_lats)
    logger.debug(f"Calculated map center: lon={center_lon}, lat={center_lat}")

    def project(lon, lat, alt):
        R = 6371000
        x = (math.radians(lon) - math.radians(center_lon)) * R * math.cos(math.radians(center_lat))
        y = alt
        z = -(math.radians(lat) - math.radians(center_lat)) * R
        return x, y, z

    projected_path = [project(lon, lat, alt) for lon, lat, alt in path_coords_ll]
    projected_geofence_corners_2d = [project(lon, lat, 0)[::2] for lon, lat in geofence_coords_ll]
    logger.debug(f"Projected {len(projected_path)} path points and {len(projected_geofence_corners_2d)} geofence corners")

    camera, scene = _setup_3d_scene()
    logger.debug("Initialized 3D scene and camera")

    if flight_path_group := _create_flight_path_group(projected_path):
        scene.add(flight_path_group)
        logger.debug("Added flight path group to scene")
    if geofence_box_group := _create_geofence_box_group(projected_geofence_corners_2d, min_alt, max_alt):
        scene.add(geofence_box_group)
        logger.debug("Added geofence box group to scene")

    # Add airplane/air traffic paths if available
    plane_points = []
    if air_traffic_data:
        plane_points = _add_air_traffic_to_3d_scene(scene, air_traffic_data, project)

    # --- Auto-framing logic ---
    framing_points = []
    if projected_path:
        framing_points.extend(projected_path)
    if projected_geofence_corners_2d:
        bottom_verts = [[x, min_alt, z] for x, z in projected_geofence_corners_2d]
        top_verts = [[x, max_alt, z] for x, z in projected_geofence_corners_2d]
        framing_points.extend(bottom_verts)
        framing_points.extend(top_verts)

    # Only use plane points for framing if we have no drone/geofence data
    # This prevents distant air traffic from ruining the scale of the drone visualization
    if not framing_points and plane_points:
        framing_points = plane_points

    if framing_points:
        points_arr = np.array(framing_points)
        min_coords = points_arr.min(axis=0)
        max_coords = points_arr.max(axis=0)

        scene_center = (min_coords + max_coords) / 2
        scene_size = max_coords - min_coords
        max_dimension = max(scene_size)

        # Position camera for a side view, looking at the center of the scene
        # Ensure a minimum distance to avoid camera being inside the object if dimension is small
        distance = max(max_dimension, 200)
        camera.position = (scene_center[0] + distance, scene_center[1] + distance * 0.5, scene_center[2])

        # The OrbitControls will orbit around this target
        controls = [three.OrbitControls(controlling=camera, target=scene_center.tolist())]
        logger.debug(f"Auto-framed scene: center={scene_center}, max_dimension={max_dimension}")
    else:
        controls = [three.OrbitControls(controlling=camera)]
        logger.debug("No points for auto-framing, using default controls")

    renderer = three.Renderer(camera=camera, scene=scene, controls=controls, width=1000, height=800)
    logger.debug("Created renderer")

    embed.embed_minimal_html(output_html_path, views=[renderer], title="3D Flight Visualization")
    logger.info(f"3D flight path visualization saved to: {output_html_path}")


if __name__ == "__main__":
    logger.info("Starting flight visualization script")
    current_dir = Path(__file__).parent
    # Use the output directory instead of current directory for generated files
    output_dir = current_dir.parent.parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Output directory set to: {output_dir}")

    conforming = ["rid_samples/flight_1_rid_aircraft_state.json", "flight_declarations_samples/flight-1-bern.json", "flight_path_map.html"]
    non_conforming = [
        "rid_samples/non-conforming/flight_1_bern_fully_nonconforming.json",
        "flight_declarations_samples/flight-1-bern.json",
        "flight_path_map_nc.html",
    ]
    partial = [
        "rid_samples/non-conforming/flight_1_bern_partially_nonconforming.json",
        "flight_declarations_samples/flight-1-bern.json",
        "flight_path_map_pn.html",
    ]

    for flight in [conforming, non_conforming, partial]:
        logger.info(f"Processing flight scenario: {flight[2].replace('.html', '')}")
        telemetry_file = current_dir / flight[0]
        declaration_file = current_dir / flight[1]
        output_file_2d = output_dir / flight[2]
        output_file_3d = output_dir / flight[2].replace(".html", "_3d.html")

        logger.debug(f"Loading telemetry from: {telemetry_file}")
        logger.debug(f"Loading declaration from: {declaration_file}")

        # Load data (assuming JSON files)
        try:
            with open(telemetry_file, "r") as f:
                telemetry_data = json.load(f)
            with open(declaration_file, "r") as f:
                declaration_data = json.load(f)
            logger.debug("Successfully loaded telemetry and declaration data")
        except Exception as e:
            logger.error(f"Failed to load data files: {e}")
            continue

        visualize_flight_path_2d(telemetry_data, declaration_data, output_file_2d)
        visualize_flight_path_3d(telemetry_data, declaration_data, output_file_3d)

    logger.info("Flight visualization script completed")
