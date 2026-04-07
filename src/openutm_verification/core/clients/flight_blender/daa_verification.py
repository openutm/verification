"""DAA verification logic for ASTM F3442 compliance checking.

Pure-function analysis of incident logs and alert data.  Extracted from
FlightBlenderClient to improve testability and reduce file complexity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

import arrow

from openutm_verification.core.reporting.reporting_models import Status, StepResult


# ---------------------------------------------------------------------------
# Internal data types
# ---------------------------------------------------------------------------
@dataclass
class _CheckResult:
    """Outcome of a single verification sub-check."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------
_ALERT_LEVEL_NAMES: dict[int, str] = {1: "ADVISORY", 2: "CAUTION", 3: "WARNING"}


def _coerce_float(value: Any) -> float | None:
    """Coerce a value to float, returning ``None`` for non-numeric inputs."""
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _parse_alert_timestamp(value: Any) -> arrow.Arrow | None:
    """Parse an alert timestamp defensively."""
    if not value:
        return None
    try:
        return arrow.get(str(value))
    except (ValueError, TypeError):
        return None


def _sort_incident_logs(incident_logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter to dicts with timestamps and sort chronologically."""
    return sorted(
        [log for log in incident_logs if isinstance(log, dict) and "timestamp" in log],
        key=lambda x: x["timestamp"],
    )


# ---------------------------------------------------------------------------
# Shared-intruder alert grouping helpers
# ---------------------------------------------------------------------------
def _new_shared_intruder_alert_summary(log: dict[str, Any], intruder_icao: str) -> dict[str, Any]:
    """Create the initial grouped summary for a shared-intruder alert."""
    timestamp = str(log["timestamp"])
    return {
        "intruder_icao": intruder_icao,
        "event_types": set(),
        "min_range_m": None,
        "first_cpa_time_seconds": None,
        "first_timestamp": timestamp,
        "last_timestamp": timestamp,
    }


def _update_shared_intruder_alert_summary(
    summary: dict[str, Any],
    log: dict[str, Any],
    intruder_icao: str,
) -> None:
    """Update grouped alert metrics from one incident-log record."""
    summary["last_timestamp"] = str(log["timestamp"])
    if intruder_icao and not summary["intruder_icao"]:
        summary["intruder_icao"] = intruder_icao

    event_type = log.get("event_type")
    if event_type:
        summary["event_types"].add(str(event_type))

    range_m = _coerce_float(log.get("range_m"))
    current_min_range = summary["min_range_m"]
    if range_m is not None and (current_min_range is None or range_m < current_min_range):
        summary["min_range_m"] = range_m

    cpa_time = _coerce_float(log.get("cpa_time_seconds"))
    if cpa_time is not None and summary["first_cpa_time_seconds"] is None:
        summary["first_cpa_time_seconds"] = cpa_time


def _summarize_shared_intruder_alerts(
    incident_logs: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Group incident logs by ``alert_id`` and collect shared-intruder metrics."""
    sorted_logs = sorted(
        [log for log in incident_logs if isinstance(log, dict) and log.get("alert_id") and log.get("timestamp")],
        key=lambda log: str(log["timestamp"]),
    )

    per_alert: dict[str, dict[str, Any]] = {}
    observed_intruders: set[str] = set()
    for log in sorted_logs:
        alert_id = str(log.get("alert_id") or "")
        intruder_icao = str(log.get("intruder_icao") or "")
        if intruder_icao:
            observed_intruders.add(intruder_icao)

        alert_summary = per_alert.setdefault(alert_id, _new_shared_intruder_alert_summary(log, intruder_icao))
        _update_shared_intruder_alert_summary(alert_summary, log, intruder_icao)

    return per_alert, observed_intruders


def _build_shared_intruder_verification_payload(
    per_alert: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[float], list[float]]:
    """Convert grouped alert data into verification-friendly summaries."""
    lifecycle_incomplete: list[str] = []
    min_ranges: list[float] = []
    first_cpas: list[float] = []
    alert_summaries: list[dict[str, Any]] = []

    for alert_id, summary in per_alert.items():
        event_types = sorted(summary["event_types"])
        if "alert_triggered" not in event_types or "alert_resolved" not in event_types:
            lifecycle_incomplete.append(alert_id)

        min_range_m = summary["min_range_m"]
        if isinstance(min_range_m, float):
            min_ranges.append(min_range_m)

        first_cpa = summary["first_cpa_time_seconds"]
        if isinstance(first_cpa, float):
            first_cpas.append(first_cpa)

        alert_summaries.append(
            {
                "alert_id": alert_id,
                "intruder_icao": summary["intruder_icao"],
                "event_types": event_types,
                "min_range_m": None if min_range_m is None else round(min_range_m, 1),
                "first_cpa_time_seconds": None if first_cpa is None else round(first_cpa, 1),
                "first_timestamp": summary["first_timestamp"],
                "last_timestamp": summary["last_timestamp"],
            }
        )

    return alert_summaries, lifecycle_incomplete, min_ranges, first_cpas


def _build_overlapping_alert_candidates(
    alert_summaries: list[dict[str, Any]],
) -> tuple[int, list[list[dict[str, Any]]]]:
    """Collect sets of simultaneously active alerts from alert summaries."""
    events: list[tuple[arrow.Arrow, int, str, dict[str, Any]]] = []
    for summary in alert_summaries:
        alert_id = str(summary.get("alert_id") or "")
        start = _parse_alert_timestamp(summary.get("first_timestamp"))
        end = _parse_alert_timestamp(summary.get("last_timestamp"))
        if not alert_id or start is None or end is None:
            continue
        if end < start:
            start, end = end, start

        # Sort starts before ends at identical timestamps so simultaneous
        # trigger/resolve boundaries still count as overlapping activity.
        events.append((start, 0, alert_id, summary))
        events.append((end, 1, alert_id, summary))

    events.sort(key=lambda item: (item[0], item[1]))

    active: dict[str, dict[str, Any]] = {}
    candidates: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    max_concurrent = 0

    for _, event_kind, alert_id, summary in events:
        if event_kind == 0:
            active[alert_id] = summary
            max_concurrent = max(max_concurrent, len(active))
            if len(active) >= 2:
                candidate_key = tuple(sorted(active))
                if candidate_key not in candidates:
                    candidates[candidate_key] = [active[key] for key in sorted(active)]
        else:
            active.pop(alert_id, None)

    return max_concurrent, list(candidates.values())


# ---------------------------------------------------------------------------
# Encounter criteria sub-checks (used by verify_encounter_criteria)
# ---------------------------------------------------------------------------
def _check_alert_escalation(
    sorted_logs: list[dict[str, Any]],
    expected_alert_levels: list[int],
) -> _CheckResult:
    """For each alert, higher alert levels should have smaller min ranges."""
    errors: list[str] = []
    sorted_expected = sorted(expected_alert_levels)
    tolerance_m = 5.0

    per_alert_ranges: dict[str, dict[int, float]] = {}
    for log in sorted_logs:
        alert_id = str(log.get("alert_id") or log.get("alert") or "")
        level = log.get("alert_level")
        range_m = log.get("range_m")
        if not alert_id or level is None or range_m is None or level == 0:
            continue
        bucket = per_alert_ranges.setdefault(alert_id, {})
        if level not in bucket or range_m < bucket[level]:
            bucket[level] = range_m

    for alert_id, min_range_by_level in per_alert_ranges.items():
        for i in range(len(sorted_expected) - 1):
            lo, hi = sorted_expected[i], sorted_expected[i + 1]
            r_lo = min_range_by_level.get(lo)
            r_hi = min_range_by_level.get(hi)
            if r_lo is not None and r_hi is not None and (r_hi - r_lo) > tolerance_m:
                errors.append(
                    f"Alert {alert_id[:8]}: min {_ALERT_LEVEL_NAMES.get(hi, f'L{hi}')} range "
                    f"({r_hi:.1f}m) > min {_ALERT_LEVEL_NAMES.get(lo, f'L{lo}')} range "
                    f"({r_lo:.1f}m) by {r_hi - r_lo:.1f}m (tolerance {tolerance_m}m)"
                )

    return _CheckResult(ok=not errors, errors=errors[:5])


def _check_expected_levels(
    sorted_logs: list[dict[str, Any]],
    expected_alert_levels: list[int],
) -> _CheckResult:
    """Verify all expected alert levels are present in the logs."""
    observed = sorted({log["alert_level"] for log in sorted_logs if isinstance(log.get("alert_level"), int) and log["alert_level"] > 0})
    missing = [lv for lv in expected_alert_levels if lv not in observed]
    warnings: list[str] = []
    if missing:
        names = [_ALERT_LEVEL_NAMES.get(lv, f"L{lv}") for lv in missing]
        warnings.append(f"Expected alert levels not observed: {', '.join(names)} {missing}")
    return _CheckResult(
        ok=True,
        warnings=warnings,
        metadata={"observed_levels": observed, "missing_levels": missing},
    )


def _check_cpa_present(sorted_logs: list[dict[str, Any]]) -> _CheckResult:
    """Check that CPA time values are present and reasonable."""
    errors: list[str] = []
    warnings: list[str] = []
    cpa_values = [log.get("cpa_time_seconds") for log in sorted_logs if log.get("cpa_time_seconds") is not None]
    if not cpa_values:
        errors.append("No CPA time values found in incident logs")
    else:
        unreasonable = [v for v in cpa_values if not isinstance(v, (int, float)) or v < 0 or v > 300]
        if unreasonable:
            warnings.append(f"Found {len(unreasonable)} CPA values outside 0-300s range")
    return _CheckResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        metadata={"cpa_values_count": len(cpa_values)},
    )


def _check_1hz_compliance(
    sorted_logs: list[dict[str, Any]],
    max_1hz_gap_seconds: float,
) -> _CheckResult:
    """Evaluate 1Hz logging cadence within each alert lifecycle (ASTM F3442 §10.2.3)."""
    errors: list[str] = []
    alert_timestamps_by_id: dict[str, list[arrow.Arrow]] = {}
    for log in sorted_logs:
        if log.get("event_type") in ("alert_triggered", "alert_updated", "periodic_update"):
            ts = _parse_alert_timestamp(log.get("timestamp"))
            if ts is None:
                continue
            alert_id = str(log.get("alert_id") or "") or "__ungrouped__"
            alert_timestamps_by_id.setdefault(alert_id, []).append(ts)

    alert_event_count = sum(len(ts) for ts in alert_timestamps_by_id.values())
    max_gap = 0.0
    hz_violation_count = 0
    hz_total_gaps = 0
    hz_compliance_pct = 100.0

    if alert_event_count >= 2:
        gaps: list[float] = []
        violating_alert_ids: set[str] = set()
        for alert_id, timestamps in alert_timestamps_by_id.items():
            sorted_ts = sorted(timestamps)
            for i in range(1, len(sorted_ts)):
                gap = (sorted_ts[i] - sorted_ts[i - 1]).total_seconds()
                gaps.append(gap)
                if gap > max_1hz_gap_seconds:
                    violating_alert_ids.add(alert_id)

        hz_total_gaps = len(gaps)
        hz_violation_count = sum(1 for g in gaps if g > max_1hz_gap_seconds)
        hz_compliance_pct = round(100.0 * (hz_total_gaps - hz_violation_count) / hz_total_gaps, 1) if hz_total_gaps else 100.0
        max_gap = max(gaps) if gaps else 0.0
        if hz_violation_count > 0:
            summaries = ", ".join(sorted(aid[:8] for aid in violating_alert_ids if aid != "__ungrouped__"))
            errors.append(
                f"1Hz logging violation: {hz_violation_count}/{hz_total_gaps} gaps exceed {max_1hz_gap_seconds}s "
                f"(max gap {max_gap:.2f}s, {hz_compliance_pct}% compliant)" + (f" across alert lifecycles {summaries}" if summaries else "")
            )
    else:
        errors.append(f"Only {alert_event_count} timestamped alert/periodic entries; cannot verify 1Hz compliance")

    return _CheckResult(
        ok=not errors,
        errors=errors,
        metadata={
            "alert_event_count": alert_event_count,
            "max_timestamp_gap_seconds": round(max_gap, 2),
            "hz_violation_count": hz_violation_count,
            "hz_total_gaps": hz_total_gaps,
            "hz_compliance_pct": hz_compliance_pct,
        },
    )


def _check_lifecycle_complete(sorted_logs: list[dict[str, Any]]) -> _CheckResult:
    """Check that alert_triggered and alert_resolved events are present."""
    errors: list[str] = []
    warnings: list[str] = []
    event_types = {str(log["event_type"]) for log in sorted_logs if log.get("event_type")}

    if "alert_triggered" not in event_types:
        errors.append("Missing alert_triggered event - alert lifecycle incomplete")
    if "alert_resolved" not in event_types:
        errors.append("Missing alert_resolved event - alert was never resolved")
    if "periodic_update" not in event_types:
        warnings.append("No periodic_update events found during conflict")

    return _CheckResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        metadata={"event_types_seen": sorted(event_types)},
    )


def _check_encounter_geometry(
    sorted_logs: list[dict[str, Any]],
    expected_geometry: str,
) -> _CheckResult:
    """Verify bearing data is consistent with the expected encounter geometry."""
    warnings: list[str] = []
    bearings = [float(log["bearing_deg"]) for log in sorted_logs if isinstance(log.get("bearing_deg"), (int, float))]

    if not bearings or expected_geometry == "any":
        return _CheckResult(ok=True)

    if expected_geometry == "head_on":
        consistent = [b for b in bearings if (b < 45 or b > 315) or (135 < b < 225)]
    elif expected_geometry == "crossing":
        consistent = [b for b in bearings if (45 <= b <= 135) or (225 <= b <= 315)]
    elif expected_geometry == "overtake":
        consistent = [b for b in bearings if 135 <= b <= 225]
    else:
        warnings.append(f"Unknown expected_geometry '{expected_geometry}', skipping geometry check")
        return _CheckResult(ok=True, warnings=warnings)

    if len(consistent) < len(bearings) * 0.5:
        warnings.append(f"Only {len(consistent)}/{len(bearings)} bearings consistent with {expected_geometry} geometry")

    # Geometry is advisory — a warning, not a hard error
    return _CheckResult(ok=True, warnings=warnings)


# ---------------------------------------------------------------------------
# Top-level verification functions
# ---------------------------------------------------------------------------
def verify_astm_f3442_compliance(
    incident_logs: list[dict[str, Any]],
    active_alerts: list[dict[str, Any]] | None = None,
    min_incident_logs: int = 1,
    require_alert_events: bool = True,
    require_periodic_updates: bool = True,
) -> StepResult:
    """Verify ASTM F3442 API payload schema and data-type correctness.

    Universal baseline check applicable to all DAA scenarios.  Validates:
    - Required field presence on incident logs and active alerts
    - Data types: alert_level is int 0-3, range_m/bearing_deg/vertical_separation_m
      are non-negative numerics, timestamp is parseable
    - Event type existence (alert lifecycle and periodic updates)
    """
    step_name = "Verify DAA ASTM F3442 API Compliance"
    errors: list[str] = []
    type_warnings: list[str] = []

    if not isinstance(incident_logs, list):
        errors.append("Incident logs payload is not a list")
        incident_logs = []

    if len(incident_logs) < min_incident_logs:
        errors.append(f"Expected at least {min_incident_logs} incident logs, got {len(incident_logs)}")

    required_incident_fields = (
        "event_type",
        "timestamp",
        "alert_level",
        "alert_status",
        "priority_rank",
        "bearing_deg",
        "range_m",
        "vertical_separation_m",
        "cpa_time_seconds",
        "is_coasted",
    )

    for idx, entry in enumerate(incident_logs):
        if not isinstance(entry, dict):
            errors.append(f"Incident log at index {idx} is not an object")
            continue
        missing_fields = [f for f in required_incident_fields if f not in entry]
        if missing_fields:
            errors.append(f"Incident log at index {idx} missing fields: {', '.join(missing_fields)}")
            continue

        al = entry.get("alert_level")
        if not isinstance(al, int) or al < 0 or al > 3:
            type_warnings.append(f"Log {idx}: alert_level={al!r} not int in 0-3")

        for numeric_field in ("range_m", "bearing_deg", "vertical_separation_m"):
            val = entry.get(numeric_field)
            if val is not None and not isinstance(val, (int, float)):
                type_warnings.append(f"Log {idx}: {numeric_field}={val!r} is not numeric")
            elif isinstance(val, (int, float)) and val < 0 and numeric_field == "range_m":
                type_warnings.append(f"Log {idx}: range_m={val} is negative")

        ts = entry.get("timestamp")
        if ts is not None:
            try:
                arrow.get(ts)
            except (ValueError, TypeError):
                type_warnings.append(f"Log {idx}: timestamp={ts!r} is not parseable")

    # Promote first 5 type warnings to errors (keeps report concise)
    if type_warnings:
        errors.extend(type_warnings[:5])
        if len(type_warnings) > 5:
            errors.append(f"... and {len(type_warnings) - 5} more data-type issues")

    event_types = sorted(
        str(entry["event_type"])
        for entry in incident_logs
        if isinstance(entry, dict) and isinstance(entry.get("event_type"), str) and entry.get("event_type")
    )
    event_types_set = set(event_types)
    if require_alert_events and not event_types_set.intersection({"alert_triggered", "alert_updated", "alert_resolved"}):
        errors.append("No alert lifecycle events found (alert_triggered/alert_updated/alert_resolved)")
    if require_periodic_updates and "periodic_update" not in event_types_set:
        errors.append("No periodic_update incident log entries found")

    if active_alerts is not None:
        if not isinstance(active_alerts, list):
            errors.append("Active alerts payload is not a list")
        else:
            required_alert_fields = ("id", "ownship_operation", "intruder_icao", "status", "current_level", "active_log_entry")
            for idx, alert in enumerate(active_alerts):
                if not isinstance(alert, dict):
                    errors.append(f"Active alert at index {idx} is not an object")
                    continue
                missing_alert_fields = [f for f in required_alert_fields if f not in alert]
                if missing_alert_fields:
                    errors.append(f"Active alert at index {idx} missing fields: {', '.join(missing_alert_fields)}")

    observed_levels: list[int] = []
    for entry in incident_logs:
        if isinstance(entry, dict):
            raw_level = entry.get("alert_level")
            if isinstance(raw_level, int):
                observed_levels.append(raw_level)

    return StepResult(
        name=step_name,
        status=Status.PASS if not errors else Status.FAIL,
        duration=0.0,
        error_message=None if not errors else "; ".join(errors),
        result={
            "incident_logs_count": len(incident_logs),
            "active_alerts_count": len(active_alerts) if isinstance(active_alerts, list) else None,
            "event_types": event_types,
            "highest_alert_level_observed": max(observed_levels) if observed_levels else None,
            "data_type_issues": len(type_warnings),
            "compliant": not errors,
        },
    )


def verify_encounter_criteria(
    incident_logs: list[dict[str, Any]],
    expected_alert_levels: list[int] | None = None,
    expected_geometry: str = "any",
    require_escalation: bool = True,
    require_cpa: bool = True,
    require_lifecycle: bool = True,
    max_1hz_gap_seconds: float = 1.0,
) -> StepResult:
    """Verify DAA encounter pass/fail criteria — parametrized for any scenario.

    Flight Blender uses predictive alerting: alert_level is based on the
    minimum predicted separation over a 30-second look-ahead horizon, while
    range_m records the current distance.

    Checks (each gated by parameters):
    1. Alert escalation: first range of each higher level <= previous level
    2. Expected alert levels present
    3. CPA calculated and logged
    4. 1Hz logging compliance with detailed violation reporting
    5. Alert lifecycle completeness (triggered -> resolved)
    6. Encounter geometry consistency
    """
    step_name = "Verify DAA Encounter Criteria"
    if expected_alert_levels is None:
        expected_alert_levels = [1, 2, 3]

    errors: list[str] = []
    warnings: list[str] = []

    if not incident_logs:
        errors.append("No incident logs found - cannot verify encounter criteria")
        return StepResult(
            name=step_name,
            status=Status.FAIL,
            duration=0.0,
            error_message="; ".join(errors),
            result={"checks": {}, "compliant": False, "errors": errors, "warnings": warnings},
        )

    sorted_logs = _sort_incident_logs(incident_logs)

    # Run sub-checks conditionally
    escalation = _check_alert_escalation(sorted_logs, expected_alert_levels) if require_escalation else _CheckResult(ok=True)
    levels = _check_expected_levels(sorted_logs, expected_alert_levels)
    cpa = _check_cpa_present(sorted_logs) if require_cpa else _CheckResult(ok=True, metadata={"cpa_values_count": 0})
    hz = _check_1hz_compliance(sorted_logs, max_1hz_gap_seconds)
    lifecycle = _check_lifecycle_complete(sorted_logs) if require_lifecycle else _CheckResult(ok=True, metadata={"event_types_seen": []})
    geometry = _check_encounter_geometry(sorted_logs, expected_geometry)

    # Aggregate errors and warnings
    for check in (escalation, levels, cpa, hz, lifecycle, geometry):
        errors.extend(check.errors)
        warnings.extend(check.warnings)

    # Build result payload
    range_values = [float(log["range_m"]) for log in sorted_logs if isinstance(log.get("range_m"), (int, float))]
    observed_levels = levels.metadata.get("observed_levels", [])

    checks = {
        "escalation": escalation.ok,
        "expected_levels_present": len(levels.metadata.get("missing_levels", [])) == 0,
        "cpa_present": cpa.ok,
        "hz_compliant": hz.ok,
        "lifecycle_complete": lifecycle.ok,
        "geometry_consistent": geometry.ok,
    }
    compliant = not errors

    return StepResult(
        name=step_name,
        status=Status.PASS if compliant else Status.FAIL,
        duration=0.0,
        error_message=None if compliant else "; ".join(errors),
        result={
            "checks": checks,
            "compliant": compliant,
            "observed_alert_levels": observed_levels,
            "expected_alert_levels": expected_alert_levels,
            "expected_geometry": expected_geometry,
            "incident_log_count": len(sorted_logs),
            "alert_event_count": hz.metadata.get("alert_event_count", 0),
            "max_timestamp_gap_seconds": hz.metadata.get("max_timestamp_gap_seconds", 0),
            "hz_violation_count": hz.metadata.get("hz_violation_count", 0),
            "hz_total_gaps": hz.metadata.get("hz_total_gaps", 0),
            "hz_compliance_pct": hz.metadata.get("hz_compliance_pct", 100.0),
            "cpa_values_count": cpa.metadata.get("cpa_values_count", 0),
            "min_range_m": round(min(range_values), 1) if range_values else None,
            "max_range_m": round(max(range_values), 1) if range_values else None,
            "highest_alert_level": max(observed_levels) if observed_levels else None,
            "event_types_seen": lifecycle.metadata.get("event_types_seen", []),
            "errors": errors,
            "warnings": warnings,
        },
    )


def verify_shared_intruder_independence(
    incident_logs: list[dict[str, Any]],
    expected_intruder_icao: str,
    expected_alert_count: int = 2,
    min_distinct_range_m: float = 25.0,
    min_distinct_initial_cpa_seconds: float = 5.0,
    allow_other_intruders: bool = False,
) -> StepResult:
    """Verify that one shared intruder generated overlapping independent alerts for multiple ownships."""
    step_name = "Verify DAA Shared Intruder Independence"
    errors: list[str] = []
    warnings: list[str] = []

    if not incident_logs:
        return StepResult(
            name=step_name,
            status=Status.FAIL,
            duration=0.0,
            error_message="No incident logs found - cannot verify shared intruder independence",
            result={"compliant": False, "errors": ["No incident logs found"], "warnings": warnings},
        )

    # When other intruders are expected, filter to only the target intruder
    if allow_other_intruders:
        filtered_logs = [log for log in incident_logs if isinstance(log, dict) and str(log.get("intruder_icao", "")) == expected_intruder_icao]
        if not filtered_logs:
            errors.append(f"Expected shared intruder '{expected_intruder_icao}' not found in incident logs")
            return StepResult(
                name=step_name,
                status=Status.FAIL,
                duration=0.0,
                error_message="; ".join(errors),
                result={"compliant": False, "errors": errors, "warnings": warnings},
            )
        per_alert, observed_intruders = _summarize_shared_intruder_alerts(filtered_logs)
    else:
        per_alert, observed_intruders = _summarize_shared_intruder_alerts(incident_logs)

    unexpected = sorted(i for i in observed_intruders if i != expected_intruder_icao)
    if expected_intruder_icao not in observed_intruders:
        errors.append(f"Expected shared intruder '{expected_intruder_icao}' not found in incident logs")
    if unexpected:
        errors.append(f"Unexpected intruder identifiers observed: {', '.join(unexpected)}")

    alert_summaries, lifecycle_incomplete, _, _ = _build_shared_intruder_verification_payload(per_alert)
    max_concurrent, overlap_candidates = _build_overlapping_alert_candidates(alert_summaries)

    if len(per_alert) > expected_alert_count:
        warnings.append(f"Observed {len(per_alert)} alert lifecycles across the scenario; using simultaneous overlap analysis")

    if max_concurrent < expected_alert_count:
        errors.append(f"Expected at least {expected_alert_count} simultaneous alerts, observed at most {max_concurrent}")

    if lifecycle_incomplete:
        errors.append("Missing complete alert lifecycle for alerts: " + ", ".join(sorted(aid[:8] for aid in lifecycle_incomplete)))

    best_overlap_candidate: dict[str, Any] | None = None
    candidate_evaluations: list[dict[str, Any]] = []
    if overlap_candidates:
        for candidate in overlap_candidates:
            if len(candidate) < expected_alert_count:
                continue
            for subset in combinations(candidate, expected_alert_count):
                candidate_min_ranges = [float(s["min_range_m"]) for s in subset if isinstance(s.get("min_range_m"), (int, float))]
                candidate_cpas = [float(s["first_cpa_time_seconds"]) for s in subset if isinstance(s.get("first_cpa_time_seconds"), (int, float))]
                range_delta = max(candidate_min_ranges) - min(candidate_min_ranges) if len(candidate_min_ranges) == expected_alert_count else None
                cpa_delta = max(candidate_cpas) - min(candidate_cpas) if len(candidate_cpas) == expected_alert_count else None
                candidate_evaluations.append(
                    {
                        "alert_ids": [str(s["alert_id"]) for s in subset],
                        "range_delta_m": None if range_delta is None else round(range_delta, 1),
                        "initial_cpa_delta_seconds": None if cpa_delta is None else round(cpa_delta, 1),
                    }
                )

        if candidate_evaluations:
            # Prefer candidates that pass both thresholds; fall back to most-distinct if none do
            passing = [
                c
                for c in candidate_evaluations
                if (c["range_delta_m"] or 0) >= min_distinct_range_m and (c["initial_cpa_delta_seconds"] or 0) >= min_distinct_initial_cpa_seconds
            ]
            pool = passing or candidate_evaluations
            best_overlap_candidate = max(
                pool,
                key=lambda c: (float(c["range_delta_m"] or -1.0), float(c["initial_cpa_delta_seconds"] or -1.0)),
            )

    if best_overlap_candidate is None:
        if max_concurrent >= expected_alert_count:
            errors.append("Could not compute overlapping alert comparisons for the simultaneous alerts")
    else:
        rd = best_overlap_candidate["range_delta_m"]
        if rd is None:
            warnings.append("Could not compute distinct minimum range comparison for simultaneous alerts")
        elif rd < min_distinct_range_m:
            errors.append(f"Simultaneous alert minimum ranges are too similar ({rd:.1f}m delta, expected at least {min_distinct_range_m:.1f}m)")

        cd = best_overlap_candidate["initial_cpa_delta_seconds"]
        if cd is None:
            warnings.append("Could not compute distinct initial CPA comparison for simultaneous alerts")
        elif cd < min_distinct_initial_cpa_seconds:
            errors.append(
                f"Simultaneous alert initial CPA times are too similar ({cd:.1f}s delta, expected at least {min_distinct_initial_cpa_seconds:.1f}s)"
            )

    compliant = not errors
    return StepResult(
        name=step_name,
        status=Status.PASS if compliant else Status.FAIL,
        duration=0.0,
        error_message=None if compliant else "; ".join(errors),
        result={
            "compliant": compliant,
            "expected_intruder_icao": expected_intruder_icao,
            "observed_intruders": sorted(observed_intruders),
            "distinct_alert_count": len(per_alert),
            "max_concurrent_alert_count": max_concurrent,
            "alert_summaries": alert_summaries,
            "overlap_candidate_count": len(overlap_candidates),
            "best_overlap_candidate": best_overlap_candidate,
            "errors": errors,
            "warnings": warnings,
        },
    )
