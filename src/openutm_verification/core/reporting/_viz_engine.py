"""Shared visualization engine for live and from-report paths.

Both ``reporting.py`` (live) and ``visualize_from_report.py`` (post-hoc)
normalize their data into plain dicts then delegate to this module.

The single entry point is :func:`render_scenario_visualizations`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from openutm_verification.core.reporting.visualize_flight import (
    visualize_flight_path_2d,
    visualize_flight_path_3d,
)

# ---------------------------------------------------------------------------
# Step-payload extraction
# ---------------------------------------------------------------------------


def extract_step_payload(steps: list[dict[str, Any]], step_id: str, step_name: str) -> Any:
    """Extract a step's ``result`` by *id* (preferred) or *name* (fallback).

    Works on plain dicts – callers must ``model_dump()`` before passing model
    objects.
    """
    for step in steps:
        if step.get("id") == step_id:
            return step.get("result")

    for step in steps:
        if step.get("name") == step_name:
            return step.get("result")

    return None


# ---------------------------------------------------------------------------
# Ownship label derivation
# ---------------------------------------------------------------------------


def label_from_step_id(step_id: str, fallback_idx: int) -> str:
    """Derive a human-friendly ownship label from a step ID.

    Pattern: ``generate_<name>_telemetry`` → ``Alpha``.
    """
    parts = step_id.replace("generate_", "").replace("_telemetry", "").split("_")
    if parts and parts[0] and parts[0] != step_id:
        return " ".join(p.capitalize() for p in parts)
    return f"Ownship {fallback_idx + 1}"


# ---------------------------------------------------------------------------
# Multi-ownship declaration resolution
# ---------------------------------------------------------------------------


def resolve_per_ownship_declarations(
    flight_declarations_data: list[dict[str, Any]] | None,
    scenario_name: str | None,
) -> list[dict[str, Any]] | None:
    """Return per-ownship declaration dicts.

    Priority:
      1. ``flight_declarations_data`` passed directly (already dicts).
      2. Reconstruct from scenario YAML + local config files.
    """
    if flight_declarations_data and isinstance(flight_declarations_data, list):
        return flight_declarations_data
    if scenario_name:
        return try_load_declarations_for_scenario(scenario_name)
    return None


def try_load_declarations_for_scenario(scenario_name: str) -> list[dict[str, Any]] | None:
    """Reconstruct per-ownship declarations from scenario YAML config files.

    Scans scenario YAML for ``declaration_paths`` (or legacy
    ``first/second_flight_declaration_path``) arguments, then generates
    FlightDeclaration dicts via ``FlightDeclarationGenerator``.
    """
    try:
        from openutm_verification.simulator.flight_declaration import FlightDeclarationGenerator

        pkg_root = Path(__file__).resolve().parents[4]
        yaml_path = pkg_root / "scenarios" / f"{scenario_name}.yaml"
        if not yaml_path.exists():
            return None

        with yaml_path.open("r", encoding="utf-8") as f:
            scenario = yaml.safe_load(f)

        for step in scenario.get("steps", []):
            args = step.get("arguments")
            if not isinstance(args, dict):
                continue

            config_paths: list[str] = []
            if "declaration_paths" in args and isinstance(args["declaration_paths"], list):
                config_paths = args["declaration_paths"]
            elif "first_flight_declaration_path" in args:
                config_paths = [args["first_flight_declaration_path"]]
                if "second_flight_declaration_path" in args:
                    config_paths.append(args["second_flight_declaration_path"])

            if not config_paths:
                continue

            declarations: list[dict[str, Any]] = []
            for config_path in config_paths:
                full_path = pkg_root / config_path
                if not full_path.exists():
                    logger.debug(f"Config file not found: {full_path}")
                    return None
                decl = FlightDeclarationGenerator(bounds_path=full_path).generate()
                declarations.append(decl.model_dump())

            if declarations:
                logger.info(f"Reconstructed {len(declarations)} per-ownship declarations from scenario '{scenario_name}'")
                return declarations

        return None
    except (OSError, ValueError, yaml.YAMLError, ImportError) as exc:
        logger.debug(f"Could not reconstruct declarations for scenario '{scenario_name}': {exc}")
        return None


# ---------------------------------------------------------------------------
# Ownship extraction from step dicts
# ---------------------------------------------------------------------------


def extract_ownships_from_steps(
    steps: list[dict[str, Any]],
    fallback_telemetry: list[Any],
    fallback_declaration: dict[str, Any],
    flight_declarations_data: list[dict[str, Any]] | None = None,
    scenario_name: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Build an ownships list and declaration-to-label mapping from step dicts.

    Returns ``(ownships_list, declaration_id_to_label_map)``.
    """
    telemetry_steps: list[dict[str, Any]] = []
    for step in steps:
        if step.get("name") == "Generate Telemetry" and isinstance(step.get("result"), list) and len(step.get("result", [])) > 0:
            telemetry_steps.append(step)

    # Extract declaration IDs from setup steps
    declaration_ids: list[str] = []
    for step in steps:
        result = step.get("result")
        if isinstance(result, dict) and "declarations" in result:
            declarations = result["declarations"]
            if isinstance(declarations, list):
                declaration_ids = [str(d.get("id", "")) for d in declarations if isinstance(d, dict) and d.get("id")]
                break

    if len(telemetry_steps) < 2:
        label = "Ownship"
        decl_map: dict[str, str] = {}
        if declaration_ids:
            for did in declaration_ids:
                decl_map[did] = label
        return (
            [{"label": label, "telemetry_data": fallback_telemetry, "declaration_data": fallback_declaration}],
            decl_map,
        )

    per_ownship_declarations = resolve_per_ownship_declarations(flight_declarations_data, scenario_name)

    ownships: list[dict[str, Any]] = []
    decl_map = {}
    for idx, step in enumerate(telemetry_steps):
        step_id = step.get("id") or ""
        label = label_from_step_id(step_id, idx)

        decl = fallback_declaration
        if per_ownship_declarations and idx < len(per_ownship_declarations):
            decl = per_ownship_declarations[idx]

        ownships.append(
            {
                "label": label,
                "telemetry_data": step["result"],
                "declaration_data": decl,
            }
        )
        if idx < len(declaration_ids):
            decl_map[declaration_ids[idx]] = label

    return ownships, decl_map


# ---------------------------------------------------------------------------
# Alert row derivation (incident logs → alert rows for HUD)
# ---------------------------------------------------------------------------


def derive_alert_rows_from_incident_logs(
    incident_logs: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Build alert rows from incident logs for replay HUD rendering.

    Derived from incident logs because the active-alerts endpoint is often
    empty at scenario end.
    """
    alert_rows: list[dict[str, Any]] = []
    for incident in incident_logs or []:
        if not isinstance(incident, dict):
            continue
        alert_rows.append(
            {
                "id": str(incident.get("alert_id") or incident.get("alert") or incident.get("id") or ""),
                "alert_id": str(incident.get("alert_id") or incident.get("alert") or incident.get("id") or ""),
                "timestamp": incident.get("timestamp"),
                "intruder_icao": incident.get("intruder_icao"),
                "ownship_label": incident.get("ownship_label"),
                "status": incident.get("alert_status"),
                "status_display": incident.get("alert_status_display"),
                "current_level": incident.get("alert_level"),
                "current_level_display": incident.get("alert_level_display"),
                "range_m": incident.get("range_m"),
                "vertical_separation_m": incident.get("vertical_separation_m"),
                "event_type": incident.get("event_type"),
                "event_type_display": incident.get("event_type_display"),
            }
        )
    return alert_rows


# ---------------------------------------------------------------------------
# Ownship label annotation
# ---------------------------------------------------------------------------


def annotate_ownship_labels(
    items: list[dict[str, Any]] | None,
    declaration_map: dict[str, str],
) -> None:
    """Annotate items in-place with ``ownship_label`` via *ownship_operation* → declaration map.

    Falls back to propagating via ``alert_id`` for items whose
    ``ownship_operation`` is missing.
    """
    if not items or not declaration_map:
        return

    alert_id_to_label: dict[str, str] = {}
    for item in items:
        ownship_op = item.get("ownship_operation") or item.get("ownship_operation_id")
        if ownship_op and ownship_op in declaration_map:
            label = declaration_map[ownship_op]
            item["ownship_label"] = label
            alert_id = item.get("alert_id") or item.get("alert") or item.get("id")
            if alert_id:
                alert_id_to_label[str(alert_id)] = label

    for item in items:
        if item.get("ownship_label"):
            continue
        alert_id = item.get("alert_id") or item.get("alert") or item.get("id")
        if alert_id and str(alert_id) in alert_id_to_label:
            item["ownship_label"] = alert_id_to_label[str(alert_id)]


# ---------------------------------------------------------------------------
# Core rendering entry point
# ---------------------------------------------------------------------------


def render_scenario_visualizations(
    *,
    scenario_name: str,
    steps: list[dict[str, Any]],
    telemetry_data: list[Any],
    declaration_data: dict[str, Any],
    output_dir: Path,
    air_traffic_data: list[Any] | None = None,
    flight_declarations_data: list[dict[str, Any]] | None = None,
    filename_prefix: str = "",
) -> tuple[Path, Path]:
    """Generate 2D + 3D visualization HTML for one scenario.

    All inputs are plain dicts/lists (no Pydantic models).

    Returns ``(vis_2d_path, vis_3d_path)``.
    """
    scenario_dir = output_dir / scenario_name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    # DAA payloads
    incident_logs_payload = extract_step_payload(steps, "get_daa_incident_logs", "Get DAA Incident Logs")
    amqp_messages_payload = extract_step_payload(steps, "Get AMQP Messages", "Get AMQP Messages")
    incident_logs = incident_logs_payload if isinstance(incident_logs_payload, list) else None
    amqp_messages = amqp_messages_payload if isinstance(amqp_messages_payload, list) else None

    # Active alerts — derive from incident logs (endpoint is often empty at scenario end)
    alert_rows = derive_alert_rows_from_incident_logs(incident_logs)

    # Multi-ownship
    ownships, declaration_map = extract_ownships_from_steps(
        steps,
        telemetry_data,
        declaration_data,
        flight_declarations_data=flight_declarations_data,
        scenario_name=scenario_name,
    )

    annotate_ownship_labels(incident_logs, declaration_map)
    annotate_ownship_labels(alert_rows, declaration_map)

    # Render
    suffix = f"_{filename_prefix}" if filename_prefix else ""
    vis_2d_path = scenario_dir / f"visualization_2d{suffix}.html"
    vis_3d_path = scenario_dir / f"visualization_3d{suffix}.html"

    visualize_flight_path_2d(telemetry_data, declaration_data, vis_2d_path, air_traffic_data, ownships=ownships)
    visualize_flight_path_3d(
        telemetry_data,
        declaration_data,
        vis_3d_path,
        air_traffic_data=air_traffic_data,
        active_alerts=alert_rows,
        incident_logs=incident_logs,
        amqp_messages=amqp_messages,
        ownships=ownships,
        declaration_map=declaration_map,
    )

    logger.info(f"Generated visualizations for '{scenario_name}'")
    return vis_2d_path, vis_3d_path
