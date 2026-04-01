"""
This script visualizes a flight path and its declared geofence from JSON files
onto an interactive map.
It reads flight telemetry data and a flight declaration, extracts the GPS
coordinates and GeoJSON polygon, and uses the Folium library to plot them on an
OpenStreetMap. The resulting map is saved as an HTML file.
Usage:
    - Ensure 'folium' is installed.
    - Run the script from the command line:
        python flight_blender_e2e_integration/visualize_flight.py
    - Open the generated '..._3d.html' file in a web browser for an interactive 3D view.
"""

import json
import math
from pathlib import Path
from typing import Any

import folium
from loguru import logger
from uas_standards.astm.f3411.v22a.api import RIDAircraftState

from openutm_verification.core.reporting._viz_3d_template import REPLAY_3D_HTML_TEMPLATE
from openutm_verification.core.reporting._viz_data import (
    AIRPLANE_COLORS,
    AIRPLANE_COLORS_3D,
    DEFAULT_NMAC_HORIZONTAL_DISTANCE_M,
    DEFAULT_NMAC_VERTICAL_DISTANCE_M,
    DEFAULT_WELL_CLEAR_HORIZONTAL_DISTANCE_M,
    DEFAULT_WELL_CLEAR_VERTICAL_DISTANCE_M,
    OWNSHIP_COLORS_2D,
    OWNSHIP_COLORS_3D,
    extract_all_geofences,
    extract_first_geofence,
    extract_observation_coords,
    extract_observation_timestamp,
    get_env_float,
    normalize_ownships_list,
    parse_timestamp_seconds,
    reorganize_air_traffic_by_aircraft,
    to_relative_replay_second,
)
from openutm_verification.core.reporting._viz_events import (
    derive_alert_events_from_incident_logs,
    estimate_ownship_t_shift,
    serialize_active_alert_events,
    serialize_amqp_message_events,
    serialize_incident_log_events,
)
from openutm_verification.simulator.models.flight_data_types import FlightObservationSchema

# Backward-compat re-export used by tests/test_altitude_units.py
_reorganize_air_traffic_by_aircraft = reorganize_air_traffic_by_aircraft


def visualize_flight_path_2d(
    telemetry_data: list[RIDAircraftState],
    declaration_data: dict,
    output_html_path: Path,
    air_traffic_data: list[list[FlightObservationSchema]] | None = None,
    well_clear_horizontal_distance_m: float | None = None,
    nmac_horizontal_distance_m: float | None = None,
    ownships: list[dict[str, Any]] | None = None,
):
    """
    Creates an interactive 2D map from flight telemetry and declaration data.

    Supports multiple ownships via the ``ownships`` parameter.  When provided,
    each ownship is drawn with a distinct color.  When omitted, a single ownship
    is derived from ``telemetry_data`` / ``declaration_data`` for backward
    compatibility.

    Args:
        telemetry_data: The flight telemetry data (used when ``ownships`` is not provided).
        declaration_data: The flight declaration data (used when ``ownships`` is not provided).
        output_html_path: The full path where the output HTML map will be saved.
        air_traffic_data: Optional air traffic data from simulators.
        well_clear_horizontal_distance_m: Well-clear horizontal boundary radius in meters.
        nmac_horizontal_distance_m: NMAC horizontal boundary radius in meters.
        ownships: Optional list of ownship dicts, each with ``label``, ``telemetry_data``,
            and ``declaration_data`` keys.  Defaults to a single-item list built from
            the legacy ``telemetry_data`` / ``declaration_data`` parameters.
    """
    logger.info("Starting 2D flight path visualization")

    wc_boundary_m = (
        float(well_clear_horizontal_distance_m)
        if well_clear_horizontal_distance_m is not None
        else get_env_float("WELL_CLEAR_HORIZONTAL_DISTANCE_M", DEFAULT_WELL_CLEAR_HORIZONTAL_DISTANCE_M)
    )
    nmac_boundary_m = (
        float(nmac_horizontal_distance_m)
        if nmac_horizontal_distance_m is not None
        else get_env_float("NMAC_HORIZONTAL_DISTANCE_M", DEFAULT_NMAC_HORIZONTAL_DISTANCE_M)
    )

    ownships_list = normalize_ownships_list(ownships, telemetry_data, declaration_data)
    geofence = extract_first_geofence(ownships_list)

    # Pre-process each ownship: extract coordinates
    all_coordinates: list[tuple[float, float]] = []
    ownship_paths: list[tuple[str, str, list[tuple[float, float, float]], list[tuple[float, float]]]] = []

    for idx, own in enumerate(ownships_list):
        color = OWNSHIP_COLORS_2D[idx % len(OWNSHIP_COLORS_2D)]
        states = own.get("telemetry_data") or []
        path_points = [
            (s["position"]["lat"], s["position"]["lng"], s["position"]["alt"]) for s in states if "position" in s and "alt" in s.get("position", {})
        ]
        coords = [(p[0], p[1]) for p in path_points]
        ownship_paths.append((own.get("label") or f"Ownship {idx + 1}", color, path_points, coords))
        all_coordinates.extend(coords)

    logger.debug(f"Extracted {len(all_coordinates)} total coordinate points across {len(ownships)} ownship(s)")
    logger.debug(f"Geofence data present: {geofence is not None}")

    if not all_coordinates and not geofence:
        logger.warning("No coordinates or geofence found in the data.")
        return

    if geofence:
        first_coord = geofence["features"][0]["geometry"]["coordinates"][0][1]
        map_center = [first_coord[1], first_coord[0]]
        logger.debug(f"Using geofence center for map: {map_center}")
    elif all_coordinates:
        lat, lng = all_coordinates[0]
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

    # Draw each ownship path with a distinct color
    for label, color, path_points_with_alt, coordinates in ownship_paths:
        if not coordinates:
            continue

        folium.PolyLine(locations=coordinates, color=color, weight=3, opacity=0.8, tooltip=f"{label} Flight Path").add_to(flight_map)
        for lat, lng, alt in path_points_with_alt:
            folium.Circle(
                location=(lat, lng),
                radius=wc_boundary_m,
                color="#1f77b4",
                weight=1,
                opacity=0.35,
                fill=False,
                tooltip=f"WC boundary: {wc_boundary_m:.0f}m",
            ).add_to(flight_map)
            folium.Circle(
                location=(lat, lng),
                radius=nmac_boundary_m,
                color="#d62728",
                weight=2,
                opacity=0.55,
                fill=False,
                tooltip=f"NMAC boundary: {nmac_boundary_m:.0f}m",
            ).add_to(flight_map)
            folium.CircleMarker(
                location=(lat, lng),
                radius=2,
                color=color,
                fill=True,
                fill_color=color,
                tooltip=f"{label}: Alt={alt:.2f}m",
            ).add_to(flight_map)
        folium.Marker(
            location=coordinates[0],
            popup=f"{label} Start: Lat={coordinates[0][0]}, Lng={coordinates[0][1]}",
            icon=folium.Icon(color="green", icon="play"),
        ).add_to(flight_map)
        folium.Marker(
            location=coordinates[-1],
            popup=f"{label} End: Lat={coordinates[-1][0]}, Lng={coordinates[-1][1]}",
            icon=folium.Icon(color="red", icon="stop"),
        ).add_to(flight_map)
        logger.debug(f"Added {label} flight path with {len(coordinates)} points")

    # Add airplane/air traffic paths if available
    if air_traffic_data:
        _add_air_traffic_to_2d_map(flight_map, air_traffic_data)

    flight_map.save(output_html_path)
    logger.info(f"2D flight path visualization saved to: {output_html_path}")


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
    aircraft_tracks = reorganize_air_traffic_by_aircraft(air_traffic_data)
    logger.debug(f"Adding {len(aircraft_tracks)} airplane tracks to 2D map")

    for idx, (icao_address, aircraft_observations) in enumerate(sorted(aircraft_tracks.items())):
        if not aircraft_observations:
            continue

        # Get color from palette (cycle if more aircraft than colors)
        color = AIRPLANE_COLORS[idx % len(AIRPLANE_COLORS)]

        # Extract path coordinates using shared helper
        path_points_with_alt = []
        for obs in aircraft_observations:
            lat, lon, alt = extract_observation_coords(obs)
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


def visualize_flight_path_3d(
    telemetry_data: list[RIDAircraftState],
    declaration_data: dict,
    output_html_path: Path,
    air_traffic_data: list[list[FlightObservationSchema]] | None = None,
    active_alerts: list[dict[str, Any]] | None = None,
    incident_logs: list[dict[str, Any]] | None = None,
    amqp_messages: list[dict[str, Any]] | None = None,
    ownships: list[dict[str, Any]] | None = None,
    declaration_map: dict[str, str] | None = None,
):
    """Creates a replayable interactive 3D visualization with second-by-second controls.

    Supports multiple ownships via the ``ownships`` parameter.  When provided,
    each ownship gets a distinct color and its own 3D track.  The HUD includes
    an ownship filter when more than one ownship is present.
    """
    logger.info("Starting replay-capable 3D flight path visualization")

    ownships_list = normalize_ownships_list(ownships, telemetry_data, declaration_data)

    # Build per-ownship samples
    per_ownship_samples: list[tuple[str, str, list[dict[str, Any]]]] = []
    all_ownship_timestamps: list[float] = []

    for idx, own in enumerate(ownships_list):
        color = OWNSHIP_COLORS_3D[idx % len(OWNSHIP_COLORS_3D)]
        label = str(own.get("label") or f"Ownship {idx + 1}")
        samples: list[dict[str, Any]] = []
        for state_idx, state in enumerate(own.get("telemetry_data") or []):
            position = state.get("position")
            if not position:
                continue
            lat = position.get("lat")
            lon = position.get("lng")
            alt = position.get("alt")
            if lat is None or lon is None or alt is None:
                continue
            ts = parse_timestamp_seconds(state.get("timestamp"))
            samples.append(
                {
                    "index_t": float(state_idx),
                    "timestamp_s": ts,
                    "lat": float(lat),
                    "lon": float(lon),
                    "alt": float(alt),
                }
            )
            if ts is not None:
                all_ownship_timestamps.append(ts)
        per_ownship_samples.append((label, color, samples))

    timeline_start_s = min(all_ownship_timestamps) if all_ownship_timestamps else None

    intruder_tracks: list[dict[str, Any]] = []
    if air_traffic_data:
        aircraft_tracks = reorganize_air_traffic_by_aircraft(air_traffic_data)
        for color_idx, (icao_address, observations) in enumerate(sorted(aircraft_tracks.items())):
            track_points: list[dict[str, float]] = []
            for idx, obs in enumerate(observations):
                lat, lon, alt = extract_observation_coords(obs)
                timestamp_s = extract_observation_timestamp(obs)
                if lat is None or lon is None:
                    continue
                track_points.append(
                    {
                        "t": float(to_relative_replay_second(timestamp_s, timeline_start_s, fallback_second=idx)),
                        "lat": float(lat),
                        "lon": float(lon),
                        "alt": alt,
                    }
                )
            if track_points:
                intruder_tracks.append(
                    {
                        "icao": icao_address,
                        "color": AIRPLANE_COLORS_3D[color_idx % len(AIRPLANE_COLORS_3D)],
                        "samples": track_points,
                    }
                )

    geofence = extract_first_geofence(ownships_list, declaration_data)
    all_geofences = extract_all_geofences(ownships_list, declaration_data)

    geofence_coords: list[list[float]] = []
    geofence_min_alt = 0.0
    geofence_max_alt = 0.0
    if geofence and geofence.get("features"):
        feature = geofence["features"][0]
        geofence_coords = feature["geometry"]["coordinates"][0][:-1]
        geofence_min_alt = float(feature["properties"]["min_altitude"]["meters"])
        geofence_max_alt = float(feature["properties"]["max_altitude"]["meters"])

    all_ownship_samples = [s for _, _, samples in per_ownship_samples for s in samples]
    all_points = all_ownship_samples + [pt for track in intruder_tracks for pt in track["samples"]]
    if not all_points and not geofence_coords:
        logger.warning("No data to visualize in 3D.")
        return

    all_lons = [point["lon"] for point in all_points] + [coord[0] for coord in geofence_coords]
    all_lats = [point["lat"] for point in all_points] + [coord[1] for coord in geofence_coords]
    if not all_lons or not all_lats:
        logger.warning("No coordinate data available for 3D centering.")
        return

    center_lon = sum(all_lons) / len(all_lons)
    center_lat = sum(all_lats) / len(all_lats)

    def project(lon: float, lat: float, alt: float) -> tuple[float, float, float]:
        earth_radius_m = 6_371_000
        x = (math.radians(lon) - math.radians(center_lon)) * earth_radius_m * math.cos(math.radians(center_lat))
        y = alt
        z = -(math.radians(lat) - math.radians(center_lat)) * earth_radius_m
        return x, y, z

    # Build projected tracks per ownship
    ownships_payload: list[dict[str, Any]] = []
    for label, color, samples in per_ownship_samples:
        track = []
        for sample in samples:
            x, y, z_val = project(sample["lon"], sample["lat"], sample["alt"])
            track.append(
                {
                    "t": to_relative_replay_second(sample.get("timestamp_s"), timeline_start_s, fallback_second=int(sample["index_t"])),
                    "x": x,
                    "y": y,
                    "z": z_val,
                }
            )
        ownships_payload.append({"label": label, "color": color, "track": track})

    intruders_payload = []
    for track in intruder_tracks:
        projected_points = []
        for sample in track["samples"]:
            x, y, z = project(sample["lon"], sample["lat"], sample["alt"])
            projected_points.append({"t": int(sample["t"]), "x": x, "y": y, "z": z})
        intruders_payload.append({"icao": track["icao"], "color": track["color"], "points": projected_points})

    geofence_payload = None
    if geofence_coords:
        corners = []
        for lon, lat in geofence_coords:
            x, _, z = project(float(lon), float(lat), 0.0)
            corners.append({"x": x, "z": z})
        geofence_payload = {"corners": corners, "min_alt": geofence_min_alt, "max_alt": geofence_max_alt}

    # Build per-ownship geofence payloads for multi-geofence rendering
    geofences_payload: list[dict[str, Any]] = []
    for label, geo in all_geofences:
        if not geo or not geo.get("features"):
            continue
        feat = geo["features"][0]
        coords = feat["geometry"]["coordinates"][0][:-1]
        projected_corners = []
        for lon, lat in coords:
            x, _, z = project(float(lon), float(lat), 0.0)
            projected_corners.append({"x": x, "z": z})
        geofences_payload.append(
            {
                "label": label,
                "corners": projected_corners,
                "min_alt": float(feat["properties"]["min_altitude"]["meters"]),
                "max_alt": float(feat["properties"]["max_altitude"]["meters"]),
            }
        )

    max_t = 0
    for own_p in ownships_payload:
        if own_p["track"]:
            max_t = max(max_t, max(int(point["t"]) for point in own_p["track"]))
    for intr in intruders_payload:
        if intr["points"]:
            max_t = max(max_t, max(int(point["t"]) for point in intr["points"]))

    incident_log_events = serialize_incident_log_events(incident_logs, timeline_start_s, fallback_second=max_t)
    if active_alerts:
        alert_events = serialize_active_alert_events(active_alerts, timeline_start_s, fallback_second=max_t)
    else:
        alert_events = derive_alert_events_from_incident_logs(incident_log_events)

    # Time-shift estimation for the first (or only) ownship
    if ownships_payload:
        first_track = ownships_payload[0]["track"]
        ownship_t_shift = estimate_ownship_t_shift(first_track, intruders_payload, incident_log_events)
        if ownship_t_shift:
            for own_p in ownships_payload:
                for point in own_p["track"]:
                    point["t"] = max(0, int(point.get("t", 0)) + ownship_t_shift)

    if alert_events:
        max_t = max(max_t, max(int(event["t"]) for event in alert_events))
    if incident_log_events:
        max_t = max(max_t, max(int(event["t"]) for event in incident_log_events))

    amqp_message_events = serialize_amqp_message_events(amqp_messages, timeline_start_s, fallback_second=max_t)
    if amqp_message_events:
        max_t = max(max_t, max(int(event["t"]) for event in amqp_message_events))

    # Build unified timeline for log-index playback (proposal §1)
    unified_timeline = sorted(
        [{**e, "_source": "incident", "_log_index": i} for i, e in enumerate(incident_log_events)]
        + [{**e, "_source": "amqp", "_log_index": i + len(incident_log_events)} for i, e in enumerate(amqp_message_events)],
        key=lambda e: (e.get("t", 0), {"alert": 0, "amqp": 1, "incident": 2}.get(e.get("_source", ""), 3)),
    )

    payload = {
        "timeline": {"max_t": max_t, "log_count": len(unified_timeline)},
        "ownships": ownships_payload,
        "intruders": intruders_payload,
        "geofence": geofence_payload,
        "geofences": geofences_payload,
        "daa_events": {
            "alerts": alert_events,
            "incident_logs": incident_log_events,
        },
        "amqp_messages": amqp_message_events,
        "unified_timeline": unified_timeline,
        "ownship_labels": [own["label"] for own in ownships_payload],
        "routing_key_to_ownship": declaration_map or {},
        "volumes": {
            "wc_horizontal_m": get_env_float("WELL_CLEAR_HORIZONTAL_DISTANCE_M", DEFAULT_WELL_CLEAR_HORIZONTAL_DISTANCE_M),
            "wc_vertical_m": get_env_float("WELL_CLEAR_VERTICAL_DISTANCE_M", DEFAULT_WELL_CLEAR_VERTICAL_DISTANCE_M),
            "nmac_horizontal_m": get_env_float("NMAC_HORIZONTAL_DISTANCE_M", DEFAULT_NMAC_HORIZONTAL_DISTANCE_M),
            "nmac_vertical_m": get_env_float("NMAC_VERTICAL_DISTANCE_M", DEFAULT_NMAC_VERTICAL_DISTANCE_M),
        },
    }

    html_content = REPLAY_3D_HTML_TEMPLATE.replace("__DATA__", json.dumps(payload))
    output_html_path.write_text(html_content, encoding="utf-8")
    logger.info(f"Replay-capable 3D flight path visualization saved to: {output_html_path}")


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
