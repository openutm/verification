"""Shared constants, helpers, and data normalization for visualization modules.

Centralizes duplicated logic from ``visualize_flight.py`` (2D + 3D) and
``visualize_from_report.py`` to satisfy DRY.
"""

from __future__ import annotations

import os
from typing import Any

import arrow

# ---------------------------------------------------------------------------
# Color palettes
# ---------------------------------------------------------------------------
AIRPLANE_COLORS = ["#FF8C00", "#FF6347", "#FFA500", "#FF4500", "#FFD700", "#FF7F50", "#FF69B4", "#DC143C"]
AIRPLANE_COLORS_3D = AIRPLANE_COLORS  # same palette, single source

OWNSHIP_COLORS_2D = ["#1f77b4", "#2ca02c", "#9467bd", "#17becf", "#e377c2", "#7f7f7f"]
OWNSHIP_COLORS_3D = ["#1f77ff", "#2ca02c", "#9467bd", "#17becf", "#e377c2"]
OWNSHIP_MARKER_COLORS_2D = ["blue", "green", "purple", "cadetblue", "pink", "gray"]

# ---------------------------------------------------------------------------
# DAA volume defaults  (ASTM F3442 §3.3)
# ---------------------------------------------------------------------------
METERS_PER_FOOT = 0.3048
DEFAULT_WELL_CLEAR_HORIZONTAL_DISTANCE_M = 2000 * METERS_PER_FOOT
DEFAULT_NMAC_HORIZONTAL_DISTANCE_M = 500 * METERS_PER_FOOT
DEFAULT_WELL_CLEAR_VERTICAL_DISTANCE_M = 250 * METERS_PER_FOOT
DEFAULT_NMAC_VERTICAL_DISTANCE_M = 100 * METERS_PER_FOOT


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------
def get_env_float(name: str, default: float) -> float:
    """Read a float environment variable with a typed default."""
    return float(os.getenv(name, str(default)))


def parse_timestamp_seconds(raw_timestamp: Any) -> float | None:
    """Parse a timestamp in RFC3339/string/numeric forms to unix seconds."""
    if raw_timestamp is None:
        return None

    if isinstance(raw_timestamp, dict):
        value = raw_timestamp.get("value")
        if isinstance(value, str):
            try:
                return arrow.get(value).float_timestamp
            except Exception:  # noqa: BLE001
                return None
        return None

    if isinstance(raw_timestamp, str):
        try:
            return arrow.get(raw_timestamp).float_timestamp
        except Exception:  # noqa: BLE001
            return None

    if isinstance(raw_timestamp, (int, float)):
        value = float(raw_timestamp)
        if value > 1e14:
            return value / 1_000_000.0
        if value > 1e11:
            return value / 1_000.0
        return value

    return None


def to_relative_replay_second(
    timestamp_s: float | None,
    timeline_start_s: float | None,
    fallback_second: int = 0,
) -> int:
    """Convert absolute unix seconds to replay-relative seconds."""
    if timestamp_s is not None and timeline_start_s is not None:
        return max(0, int(round(timestamp_s - timeline_start_s)))
    return max(0, int(fallback_second))


def to_float_or_none(value: Any) -> float | None:
    """Best-effort conversion to float for numeric display fields."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def to_json_safe(value: Any) -> Any:
    """Recursively convert arbitrary payloads into JSON-serializable structures."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): to_json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_safe(item) for item in value]
    return str(value)


# ---------------------------------------------------------------------------
# Data normalization
# ---------------------------------------------------------------------------
def normalize_ownships_list(
    ownships: list[dict[str, Any]] | None,
    telemetry_data: Any,
    declaration_data: Any,
) -> list[dict[str, Any]]:
    """Build a canonical ownships list, falling back to a single-entry legacy list."""
    if ownships:
        return list(ownships)
    return [{"label": "Ownship", "telemetry_data": telemetry_data, "declaration_data": declaration_data}]


def extract_first_geofence(
    ownships_list: list[dict[str, Any]],
    fallback_declaration: Any = None,
) -> dict | None:
    """Return the first geofence found across ownship declarations."""
    for own in ownships_list:
        decl = own.get("declaration_data")
        if isinstance(decl, dict) and decl.get("flight_declaration_geo_json"):
            return decl["flight_declaration_geo_json"]
    if isinstance(fallback_declaration, dict):
        return fallback_declaration.get("flight_declaration_geo_json")
    return None


def extract_all_geofences(
    ownships_list: list[dict[str, Any]],
    fallback_declaration: Any = None,
) -> list[tuple[str, dict]]:
    """Return all (label, geojson) pairs found across ownship declarations.

    Deduplicates geofences that share the same geometry (by feature coordinates)
    so shared declarations don't produce overlapping volumes.  Falls back to a
    single geofence from the fallback declaration if no per-ownship geofences
    are found.
    """
    geofences: list[tuple[str, dict]] = []
    seen_coords: set[str] = set()
    for own in ownships_list:
        decl = own.get("declaration_data")
        label = own.get("label", "Ownship")
        if isinstance(decl, dict) and decl.get("flight_declaration_geo_json"):
            geo = decl["flight_declaration_geo_json"]
            # Deduplicate by stringified feature coordinates
            features = geo.get("features", []) if isinstance(geo, dict) else []
            coord_key = str([f.get("geometry", {}).get("coordinates") for f in features if isinstance(f, dict)])
            if coord_key not in seen_coords:
                seen_coords.add(coord_key)
                geofences.append((label, geo))

    if not geofences and isinstance(fallback_declaration, dict):
        geo = fallback_declaration.get("flight_declaration_geo_json")
        if geo:
            geofences.append(("Ownship", geo))

    return geofences


# ---------------------------------------------------------------------------
# Air-traffic helpers
# ---------------------------------------------------------------------------
def reorganize_air_traffic_by_aircraft(
    air_traffic_data: list[Any],
) -> dict[str, list]:
    """Reorganize air traffic from timestamp-based to aircraft-based grouping.

    Handles both dict and Pydantic model observation formats.
    """
    aircraft_tracks: dict[str, list] = {}

    for obs in air_traffic_data:
        # Flatten nested lists from legacy report format (list[list[dict]])
        if isinstance(obs, list):
            for inner_obs in obs:
                _add_observation_to_tracks(aircraft_tracks, inner_obs)
        else:
            _add_observation_to_tracks(aircraft_tracks, obs)

    return aircraft_tracks


def _add_observation_to_tracks(tracks: dict[str, list], obs: Any) -> None:
    """Add a single observation to the aircraft tracks dict."""
    if isinstance(obs, dict):
        icao = obs.get("icao_address", "UNKNOWN")
    else:
        icao = obs.icao_address
    if icao not in tracks:
        tracks[icao] = []
    tracks[icao].append(obs)


def extract_observation_coords(obs: Any) -> tuple[float | None, float | None, float]:
    """Extract (lat, lon, alt_meters) from a flight observation (dict or Pydantic).

    Altitude is converted from mm to meters.
    """
    if isinstance(obs, dict):
        lat = obs.get("lat_dd")
        lon = obs.get("lon_dd")
        alt = (obs.get("altitude_mm", 0) or 0) / 1000
    else:
        lat = obs.lat_dd
        lon = obs.lon_dd
        alt = (obs.altitude_mm or 0) / 1000
    return lat, lon, alt


def extract_observation_timestamp(obs: Any) -> float | None:
    """Extract a parsed timestamp from a flight observation (dict or Pydantic)."""
    if isinstance(obs, dict):
        raw = obs.get("timestamp") or obs.get("created_at") or obs.get("last_seen")
    else:
        raw = getattr(obs, "timestamp", None) or getattr(obs, "created_at", None) or getattr(obs, "last_seen", None)
    return parse_timestamp_seconds(raw)
