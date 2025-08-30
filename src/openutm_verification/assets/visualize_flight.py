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

import numpy as np

try:
    import pandas as pd
except ImportError:
    print("This script requires pandas. Please install it using 'pip install pandas'")
    exit()

try:
    import ipywidgets
    import pythreejs as three
    from ipywidgets import embed
except ImportError:
    print("This script requires pythreejs and ipywidgets. Please install them using 'pip install pythreejs ipywidgets'")
    exit()

import folium


def visualize_flight_path_2d(telemetry_file_path, declaration_file_path, output_html_path):
    """
    Reads flight data and declaration from JSON files and creates an interactive 2D map.

    Args:
        telemetry_file_path (str): The full path to the flight telemetry JSON file.
        declaration_file_path (str): The full path to the flight declaration JSON file.
        output_html_path (str): The full path where the output HTML map will be saved.
    """
    try:
        with open(telemetry_file_path, "r") as f:
            telemetry_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading telemetry file {telemetry_file_path}: {e}")
        return

    try:
        with open(declaration_file_path, "r") as f:
            declaration_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading declaration file {declaration_file_path}: {e}")
        return

    states = telemetry_data.get("current_states", [])
    path_points_with_alt = [
        (s["position"]["lat"], s["position"]["lng"], s["position"]["alt"]) for s in states if "position" in s and "alt" in s["position"]
    ]
    coordinates = [(p[0], p[1]) for p in path_points_with_alt]
    geofence = declaration_data.get("flight_declaration_geo_json")

    if not coordinates and not geofence:
        print("No coordinates or geofence found in the JSON files.")
        return

    if geofence:
        first_coord = geofence["features"][0]["geometry"]["coordinates"][0][1]
        map_center = [first_coord[1], first_coord[0]]
    elif coordinates:
        map_center = coordinates[0]
    else:
        map_center = [46.97, 7.47]

    flight_map = folium.Map(location=map_center, zoom_start=15)

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

    flight_map.save(output_html_path)
    print(f"2D flight path visualization saved to: {output_html_path}")


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


def visualize_flight_path_3d(telemetry_file_path, declaration_file_path, output_html_path):
    """Creates an interactive 3D visualization of the flight path and geofence."""
    try:
        with open(telemetry_file_path, "r") as f:
            telemetry_data = json.load(f)
        with open(declaration_file_path, "r") as f:
            declaration_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading data file: {e}")
        return

    states = telemetry_data.get("current_states", [])
    path_coords_ll = [[s["position"]["lng"], s["position"]["lat"], s["position"]["alt"]] for s in states if "position" in s]
    geofence = declaration_data.get("flight_declaration_geo_json")
    geofence_coords_ll, min_alt, max_alt = [], 0, 0
    if geofence and geofence.get("features"):
        feature = geofence["features"][0]
        geofence_coords_ll = feature["geometry"]["coordinates"][0][:-1]
        min_alt = feature["properties"]["min_altitude"]["meters"]
        max_alt = feature["properties"]["max_altitude"]["meters"]

    if not path_coords_ll and not geofence_coords_ll:
        print("No data to visualize in 3D.")
        return

    all_lons = [p[0] for p in path_coords_ll] + [p[0] for p in geofence_coords_ll]
    all_lats = [p[1] for p in path_coords_ll] + [p[1] for p in geofence_coords_ll]
    if not all_lons:
        return
    center_lon, center_lat = sum(all_lons) / len(all_lons), sum(all_lats) / len(all_lats)

    def project(lon, lat, alt):
        R = 6371000
        x = (math.radians(lon) - math.radians(center_lon)) * R * math.cos(math.radians(center_lat))
        y = alt
        z = -(math.radians(lat) - math.radians(center_lat)) * R
        return x, y, z

    projected_path = [project(lon, lat, alt) for lon, lat, alt in path_coords_ll]
    projected_geofence_corners_2d = [project(lon, lat, 0)[::2] for lon, lat in geofence_coords_ll]

    camera, scene = _setup_3d_scene()

    # --- Auto-framing logic ---
    all_points = []
    if projected_path:
        all_points.extend(projected_path)
    if projected_geofence_corners_2d:
        bottom_verts = [[x, min_alt, z] for x, z in projected_geofence_corners_2d]
        top_verts = [[x, max_alt, z] for x, z in projected_geofence_corners_2d]
        all_points.extend(bottom_verts)
        all_points.extend(top_verts)

    if all_points:
        points_arr = np.array(all_points)
        min_coords = points_arr.min(axis=0)
        max_coords = points_arr.max(axis=0)

        scene_center = (min_coords + max_coords) / 2
        scene_size = max_coords - min_coords
        max_dimension = max(scene_size)

        # Position camera for a side view, looking at the center of the scene
        distance = max_dimension
        camera.position = (scene_center[0] + distance, scene_center[1] + distance * 0.5, scene_center[2])

        # The OrbitControls will orbit around this target
        controls = [three.OrbitControls(controlling=camera, target=scene_center.tolist())]
    else:
        controls = [three.OrbitControls(controlling=camera)]

    if flight_path_group := _create_flight_path_group(projected_path):
        scene.add(flight_path_group)
    if geofence_box_group := _create_geofence_box_group(projected_geofence_corners_2d, min_alt, max_alt):
        scene.add(geofence_box_group)

    renderer = three.Renderer(camera=camera, scene=scene, controls=controls, width=1000, height=800)

    embed.embed_minimal_html(output_html_path, views=[renderer], title="3D Flight Visualization")
    print(f"3D flight path visualization saved to: {output_html_path}")


if __name__ == "__main__":
    current_dir = Path(__file__).parent
    # Use the output directory instead of current directory for generated files
    output_dir = current_dir.parent.parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

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
        telemetry_file = current_dir / flight[0]
        declaration_file = current_dir / flight[1]
        output_file_2d = output_dir / flight[2]
        output_file_3d = output_dir / flight[2].replace(".html", "_3d.html")

        visualize_flight_path_2d(telemetry_file, declaration_file, output_file_2d)
        visualize_flight_path_3d(telemetry_file, declaration_file, output_file_3d)
