"""Event serialization for DAA replay HUD rendering.

Extracted from ``visualize_flight.py`` to satisfy SRP — event normalization
is independent of rendering.
"""

from __future__ import annotations

import bisect
import math
from typing import Any

from loguru import logger

from openutm_verification.core.reporting._viz_data import (
    parse_timestamp_seconds,
    to_float_or_none,
    to_json_safe,
    to_relative_replay_second,
)


# ---------------------------------------------------------------------------
# Active-alert serialization
# ---------------------------------------------------------------------------
def serialize_active_alert_events(
    active_alerts: list[dict[str, Any]] | None,
    timeline_start_s: float | None,
    fallback_second: int,
) -> list[dict[str, Any]]:
    """Normalize active-alert payload entries for replay HUD rendering."""
    events: list[dict[str, Any]] = []

    for alert in active_alerts or []:
        if not isinstance(alert, dict):
            continue

        raw_active_log_entry = alert.get("active_log_entry")
        active_log_entry: dict[str, Any] = raw_active_log_entry if isinstance(raw_active_log_entry, dict) else {}
        raw_timestamp = (
            alert.get("last_updated_at")
            or active_log_entry.get("timestamp")
            or alert.get("created_at")
            or alert.get("resolved_at")
            or alert.get("timestamp")
        )
        timestamp_s = parse_timestamp_seconds(raw_timestamp)

        events.append(
            {
                "t": to_relative_replay_second(timestamp_s, timeline_start_s, fallback_second),
                "timestamp": str(raw_timestamp) if raw_timestamp is not None else None,
                "id": str(alert.get("id", "")),
                "intruder_icao": str(alert.get("intruder_icao", "")),
                "ownship_label": alert.get("ownship_label"),
                "status": alert.get("status"),
                "status_display": alert.get("status_display"),
                "current_level": alert.get("current_level"),
                "current_level_display": alert.get("current_level_display"),
                "range_m": to_float_or_none(active_log_entry.get("range_m")),
                "vertical_separation_m": to_float_or_none(active_log_entry.get("vertical_separation_m")),
                "event_type": active_log_entry.get("event_type"),
                "event_type_display": active_log_entry.get("event_type_display"),
                "raw": to_json_safe(alert),
            }
        )

    events.sort(key=lambda event: (event.get("t", 0), event.get("id", "")))
    return events


# ---------------------------------------------------------------------------
# Incident-log serialization
# ---------------------------------------------------------------------------
def serialize_incident_log_events(
    incident_logs: list[dict[str, Any]] | None,
    timeline_start_s: float | None,
    fallback_second: int,
) -> list[dict[str, Any]]:
    """Normalize incident-log payload entries for replay HUD rendering."""
    events: list[dict[str, Any]] = []

    for incident in incident_logs or []:
        if not isinstance(incident, dict):
            continue

        raw_timestamp = incident.get("timestamp")
        timestamp_s = parse_timestamp_seconds(raw_timestamp)

        events.append(
            {
                "t": to_relative_replay_second(timestamp_s, timeline_start_s, fallback_second),
                "timestamp": str(raw_timestamp) if raw_timestamp is not None else None,
                "id": str(incident.get("id", "")),
                "alert_id": str(incident.get("alert_id") or incident.get("alert") or ""),
                "intruder_icao": incident.get("intruder_icao"),
                "ownship_label": incident.get("ownship_label"),
                "event_type": incident.get("event_type"),
                "event_type_display": incident.get("event_type_display"),
                "alert_level": incident.get("alert_level"),
                "alert_level_display": incident.get("alert_level_display"),
                "alert_status": incident.get("alert_status"),
                "alert_status_display": incident.get("alert_status_display"),
                "bearing_deg": to_float_or_none(incident.get("bearing_deg")),
                "range_m": to_float_or_none(incident.get("range_m")),
                "vertical_separation_m": to_float_or_none(incident.get("vertical_separation_m")),
                "cpa_time_seconds": to_float_or_none(incident.get("cpa_time_seconds")),
                "intruder_speed_mps": to_float_or_none(incident.get("intruder_speed_mps")),
                "intruder_heading_deg": to_float_or_none(incident.get("intruder_heading_deg")),
                "intruder_vertical_speed_mps": to_float_or_none(incident.get("intruder_vertical_speed_mps")),
                "raw": to_json_safe(incident),
            }
        )

    events.sort(key=lambda event: (event.get("t", 0), event.get("id", "")))
    return events


# ---------------------------------------------------------------------------
# Derive alert events from incident logs (fallback when endpoint is empty)
# ---------------------------------------------------------------------------
def derive_alert_events_from_incident_logs(
    incident_log_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Derive alert HUD events from incident-log timeline.

    Used when the active-alert endpoint is empty at scenario end.
    """
    derived_events: list[dict[str, Any]] = []

    for event in incident_log_events:
        event_type = str(event.get("event_type") or "").strip().lower()
        if event_type == "periodic_update":
            continue

        level = event.get("alert_level")
        status = event.get("alert_status")
        if level is None and status is None:
            continue

        alert_id = event.get("alert_id")
        if not alert_id:
            fallback_id = event.get("id")
            alert_id = str(fallback_id) if fallback_id else ""

        derived_events.append(
            {
                "t": int(event.get("t", 0)),
                "timestamp": event.get("timestamp"),
                "id": str(alert_id),
                "alert_id": str(alert_id),
                "intruder_icao": event.get("intruder_icao"),
                "ownship_label": event.get("ownship_label"),
                "status": status,
                "status_display": event.get("alert_status_display"),
                "current_level": level,
                "current_level_display": event.get("alert_level_display"),
                "range_m": event.get("range_m"),
                "vertical_separation_m": event.get("vertical_separation_m"),
                "event_type": event.get("event_type"),
                "event_type_display": event.get("event_type_display"),
                "raw": to_json_safe(event.get("raw") or event),
            }
        )

    derived_events.sort(key=lambda row: (row.get("t", 0), row.get("id", "")))
    return derived_events


# ---------------------------------------------------------------------------
# AMQP message serialization
# ---------------------------------------------------------------------------
def serialize_amqp_message_events(
    amqp_messages: list[dict[str, Any]] | None,
    timeline_start_s: float | None,
    fallback_second: int,
) -> list[dict[str, Any]]:
    """Normalize AMQP step payload entries for replay HUD rendering."""
    events: list[dict[str, Any]] = []

    for index, message in enumerate(amqp_messages or []):
        if not isinstance(message, dict):
            continue

        body = message.get("body")
        body_body: Any = None
        body_timestamp: Any = None
        body_level: Any = None

        if isinstance(body, dict):
            body_body = body.get("body")
            body_timestamp = body.get("timestamp")
            body_level = body.get("level")
        else:
            body_body = body

        raw_timestamp = body_timestamp or message.get("timestamp")
        timestamp_s = parse_timestamp_seconds(raw_timestamp)

        events.append(
            {
                "t": to_relative_replay_second(timestamp_s, timeline_start_s, fallback_second + index),
                "timestamp": str(raw_timestamp) if raw_timestamp is not None else None,
                "routing_key": message.get("routing_key"),
                "exchange": message.get("exchange"),
                "level": body_level,
                "body_body": to_json_safe(body_body),
                "raw": to_json_safe(message),
            }
        )

    events.sort(key=lambda event: (event.get("t", 0), event.get("timestamp") or ""))
    return events


# ---------------------------------------------------------------------------
# Ownship time-shift estimator
# ---------------------------------------------------------------------------
def estimate_ownship_t_shift(
    ownship_track: list[dict[str, Any]],
    intruders_payload: list[dict[str, Any]],
    incident_log_events: list[dict[str, Any]],
) -> int:
    """Estimate a small ownship replay-time shift from periodic incident ranges.

    DAA incident ranges are computed from server-ingested observations. In some
    deployments, ownship telemetry is ingested asynchronously and can lag the
    client-side submission timeline by a small amount. This estimator finds an
    integer-second shift that best aligns geometric replay distance with
    ``periodic_update`` incident ``range_m`` values.
    """
    if not ownship_track or not intruders_payload or not incident_log_events:
        return 0

    periodic_events = [
        event
        for event in incident_log_events
        if str(event.get("event_type") or "").strip().lower() == "periodic_update" and to_float_or_none(event.get("range_m")) is not None
    ]
    if len(periodic_events) < 10:
        return 0

    intruder_map: dict[str, list[dict[str, Any]]] = {}
    for intruder in intruders_payload:
        icao = str(intruder.get("icao") or "").strip()
        points = intruder.get("points")
        if not icao or not isinstance(points, list) or not points:
            continue
        intruder_map[icao] = sorted(points, key=lambda p: int(p.get("t", 0)))

    if not intruder_map:
        return 0

    own_sorted = sorted(ownship_track, key=lambda p: int(p.get("t", 0)))
    own_ts = [int(point.get("t", 0)) for point in own_sorted]

    def _latest_point(points: list[dict[str, Any]], point_ts: list[int], t_val: int) -> dict[str, Any] | None:
        idx = bisect.bisect_right(point_ts, t_val) - 1
        if idx < 0:
            return None
        return points[idx]

    intruder_ts_cache = {icao: [int(point.get("t", 0)) for point in points] for icao, points in intruder_map.items()}

    def _mae_for_shift(shift_s: int) -> tuple[float, int]:
        total_error = 0.0
        count = 0

        for event in periodic_events:
            event_t = int(event.get("t", 0))
            expected_range = to_float_or_none(event.get("range_m"))
            if expected_range is None:
                continue

            intruder_icao = str(event.get("intruder_icao") or "").strip()
            intruder_points = intruder_map.get(intruder_icao)
            intruder_ts = intruder_ts_cache.get(intruder_icao)
            if intruder_points is None or intruder_ts is None:
                first_icao = next(iter(intruder_map.keys()))
                intruder_points = intruder_map[first_icao]
                intruder_ts = intruder_ts_cache[first_icao]

            own_point = _latest_point(own_sorted, own_ts, event_t - shift_s)
            intruder_point = _latest_point(intruder_points, intruder_ts, event_t)
            if own_point is None or intruder_point is None:
                continue

            dx = float(own_point.get("x", 0.0)) - float(intruder_point.get("x", 0.0))
            dy = float(own_point.get("y", 0.0)) - float(intruder_point.get("y", 0.0))
            dz = float(own_point.get("z", 0.0)) - float(intruder_point.get("z", 0.0))
            replay_range = math.sqrt(dx * dx + dy * dy + dz * dz)

            total_error += abs(expected_range - replay_range)
            count += 1

        if count == 0:
            return float("inf"), 0
        return total_error / count, count

    baseline_mae, baseline_count = _mae_for_shift(0)
    if baseline_count < 10:
        return 0

    best_shift = 0
    best_mae = baseline_mae

    for candidate_shift in range(-8, 9):
        if candidate_shift == 0:
            continue
        candidate_mae, candidate_count = _mae_for_shift(candidate_shift)
        if candidate_count < 10:
            continue
        if candidate_mae < best_mae:
            best_mae = candidate_mae
            best_shift = candidate_shift

    if best_shift != 0 and (baseline_mae - best_mae) >= 5.0:
        logger.info(f"Applying ownship replay time shift of {best_shift}s (incident-range MAE {baseline_mae:.1f}m -> {best_mae:.1f}m)")
        return best_shift

    return 0
