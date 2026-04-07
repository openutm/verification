import json
import shutil
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any, TypeVar

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

from openutm_verification.core.execution.config_models import AppConfig, ReportingConfig
from openutm_verification.core.flight_phase import FLIGHT_PHASE_LABELS
from openutm_verification.core.reporting._viz_engine import (
    extract_step_payload,
    label_from_step_id,
    render_scenario_visualizations,
    try_load_declarations_for_scenario,
)
from openutm_verification.core.reporting.reporting_models import (
    ReportData,
    ReportSummary,
    ScenarioResult,
    Status,
)
from openutm_verification.utils.time_utils import get_run_timestamp_str

T = TypeVar("T")


def _mask_url_password(url: str) -> str:
    """Mask password in URL if present (e.g., amqp://user:password@host)."""
    import re

    # Match URLs with credentials: scheme://user:password@host
    pattern = r"((?:amqp|amqps|http|https|rabbitmq)://[^:]+:)([^@]+)(@.+)"
    match = re.match(pattern, url, re.IGNORECASE)
    if match:
        return f"{match.group(1)}***MASKED***{match.group(3)}"
    return url


def _sanitize_config(data: Any) -> Any:
    """
    Recursively sanitize sensitive fields in the configuration data.
    """
    sensitive_mask = "***MASKED***"
    sensitive_keys = ["client_id", "client_secret", "audience", "scopes", "password", "token"]
    # Keys that may contain URLs with embedded passwords
    url_keys = ["url", "amqp_url", "connection_string", "broker_url"]

    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if key in sensitive_keys:
                sanitized[key] = sensitive_mask
            elif key.lower() in url_keys and isinstance(value, str) and "@" in value:
                # URL with potential embedded credentials
                sanitized[key] = _mask_url_password(value)
            else:
                sanitized[key] = _sanitize_config(value)
        return sanitized
    elif isinstance(data, list):
        return [_sanitize_config(item) for item in data]
    elif isinstance(data, str) and "://" in data and "@" in data:
        # Standalone URL string with potential credentials
        return _mask_url_password(data)
    else:
        return data


def create_report_data(
    config: AppConfig,
    config_path: str,
    results: list[ScenarioResult],
    start_time: datetime,
    end_time: datetime,
    run_id: str | None = None,
    docs_dir: str | None = None,
) -> ReportData:
    """
    Creates validation and validation report data from run results.
    """
    sanitized_config = _sanitize_config(config.model_dump())

    try:
        tool_version = version("openutm-verification")
    except Exception:
        tool_version = "unknown"

    failed_scenarios = sum(1 for r in results if r.status == Status.FAIL)
    overall_status = Status.FAIL if failed_scenarios > 0 else Status.PASS

    return ReportData(
        run_id=run_id or config.run_id,
        tool_version=tool_version,
        start_time=start_time,
        end_time=end_time,
        total_duration=(end_time - start_time).total_seconds(),
        overall_status=overall_status,
        flight_blender_url=config.flight_blender.url,
        deployment_details=config.reporting.deployment_details,
        config_file=config_path,
        config=sanitized_config,
        results=results,
        summary=ReportSummary(
            total_scenarios=len(results),
            passed=sum(1 for r in results if r.status == Status.PASS),
            failed=failed_scenarios,
        ),
        docs_dir=docs_dir,
    )


def generate_reports(
    report_data: ReportData,
    reporting_config: ReportingConfig,
    base_filename: str = "report",
):
    """
    Generates reports based on the provided configuration.
    """
    output_dir = Path(reporting_config.output_dir)
    reporting_config.timestamp_subdir = reporting_config.timestamp_subdir or get_run_timestamp_str(datetime.now(timezone.utc))
    output_dir = output_dir / reporting_config.timestamp_subdir
    output_dir.mkdir(parents=True, exist_ok=True)

    _save_scenario_data(report_data, output_dir)

    formats = reporting_config.formats
    if "json" in formats:
        json_report_path = _generate_json_report(report_data, output_dir, base_filename)
        logger.info(f"JSON report saved to: {json_report_path}")

    if "html" in formats:
        html_report_path = _generate_html_report(report_data, output_dir, base_filename)
        logger.info(f"HTML report saved to: {html_report_path}")


def _generate_json_report(report_data: ReportData, output_dir: Path, base_filename: str):
    """
    Generates a JSON report from the collected scenario results.

    Args:
        report_data: A Pydantic model containing all the data for the report.
        output_dir: The directory where the report will be saved.
        base_filename: The base name for the report file (without extension).
    """
    report_path = output_dir / f"{base_filename}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_data.model_dump_json(indent=2))
    return report_path


def _copy_docs_images(report_data: ReportData, output_dir: Path):
    """
    Copies images from the docs source directory to the report output directory.
    """
    if not report_data.docs_dir:
        return

    source_dir = Path(report_data.docs_dir)
    extensions = {".png", ".jpg", ".jpeg", ".gif", ".svg"}

    for file_path in source_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in extensions:
            # Preserve directory structure
            relative_path = file_path.relative_to(source_dir)
            dest_path = output_dir / relative_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(file_path, dest_path)
                logger.debug(f"Copied image {relative_path} to report directory")
            except Exception as e:
                logger.warning(f"Failed to copy image {file_path}: {e}")


def _generate_html_report(report_data: ReportData, output_dir: Path, base_filename: str):
    """
    Generates an HTML report from the collected scenario results using a Jinja2 template.

    Args:
        report_data: A Pydantic model containing all the data for the report.
        output_dir: The directory where the report will be saved.
        base_filename: The base name for the report file (without extension).
    """
    # Generate visualizations for scenarios with flight data
    _generate_visualizations(report_data, output_dir)
    # Copy images referenced in docs
    _copy_docs_images(report_data, output_dir)

    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(enabled_extensions=("html", "xml"), default_for_string=True, default=True),
    )
    env.filters["markdown"] = lambda text: markdown.markdown(text) if text else ""
    env.filters["default_phase"] = lambda steps: [{**s, "phase": s.get("phase") or ""} for s in steps]
    template = env.get_template("report_template.html")

    html_content = template.render(
        report_data=report_data.model_dump(mode="json"),
        phase_labels={k.value: v for k, v in FLIGHT_PHASE_LABELS.items()},
    )

    report_path = output_dir / f"{base_filename}.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return report_path


def _steps_to_dicts(steps: list[Any]) -> list[dict[str, Any]]:
    """Normalize StepResult models to plain dicts for the shared engine."""
    out: list[dict[str, Any]] = []
    for step in steps:
        if isinstance(step, dict):
            out.append(step)
        elif hasattr(step, "model_dump"):
            out.append(step.model_dump(mode="json"))
        else:
            out.append({"id": getattr(step, "id", None), "name": getattr(step, "name", None), "result": getattr(step, "result", None)})
    return out


def _generate_scenario_visualizations(result: ScenarioResult, output_dir: Path):
    """Generate 2D and 3D visualizations for a single scenario."""
    if result.flight_declaration_data is None or result.telemetry_data is None:
        return

    flight_declaration_dict = result.flight_declaration_data.model_dump()
    steps_dicts = _steps_to_dicts(result.steps)

    # Build per-ownship declaration dicts
    all_declarations_dicts: list[dict[str, Any]] | None = None
    if result.flight_declarations_data:
        all_declarations_dicts = [d.model_dump() for d in result.flight_declarations_data]
    if not all_declarations_dicts:
        all_declarations_dicts = try_load_declarations_for_scenario(result.name)

    vis_2d, vis_3d = render_scenario_visualizations(
        scenario_name=result.name,
        steps=steps_dicts,
        telemetry_data=result.telemetry_data,
        declaration_data=flight_declaration_dict,
        output_dir=output_dir,
        air_traffic_data=result.air_traffic_data,
        flight_declarations_data=all_declarations_dicts,
    )
    result.visualization_2d_path = str(vis_2d.relative_to(output_dir))
    result.visualization_3d_path = str(vis_3d.relative_to(output_dir))


def _generate_visualizations(report_data: ReportData, output_dir: Path):
    """
    Generates flight visualizations for scenarios that have flight data.

    Args:
        report_data: The report data containing scenario results.
        output_dir: The directory where visualizations will be saved.
    """
    for result in report_data.results:
        # Try to get data from in-memory fields first, fall back to loading from files
        if result.flight_declaration_data is not None and result.telemetry_data is not None:
            telemetry_data = result.telemetry_data
            declaration_data = result.flight_declaration_data
        else:
            continue  # No data available for visualization

        if telemetry_data and declaration_data:
            try:
                _generate_scenario_visualizations(result, output_dir)
            except Exception as e:
                logger.warning(f"Failed to generate visualizations for scenario '{result.name}': {e}")


def _write_json(directory: Path, filename: str, data: Any) -> None:
    """Write *data* as indented JSON to *directory/filename*."""
    path = directory / filename
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.debug(f"Saved {filename} to {path}")


def _save_per_ownship_telemetry(steps: list[dict[str, Any]], scenario_dir: Path) -> None:
    """Extract and persist per-ownship telemetry from Generate Telemetry steps."""
    telem_idx = 0
    for step in steps:
        result = step.get("result")
        if step.get("name") != "Generate Telemetry" or not isinstance(result, list) or not result:
            continue
        step_id = step.get("id") or ""
        label = label_from_step_id(step_id, telem_idx).lower().replace(" ", "_")
        _write_json(scenario_dir, f"telemetry_{label}.json", result)
        telem_idx += 1


def _save_scenario_data(report_data: ReportData, output_dir: Path):
    """Save generated data for each scenario in a subdirectory.

    Produces:
      - ``flight_declaration.json`` – primary (first) declaration
      - ``flight_declaration_<idx>.json`` – each declaration for multi-ownship
      - ``telemetry.json`` – primary (combined) telemetry
      - ``telemetry_<label>.json`` – per-ownship telemetry from Generate Telemetry steps
      - ``air_traffic.json`` – intruder / air-traffic observations
      - ``incident_logs.json`` – DAA incident logs (if present)
      - ``active_alerts.json`` – active DAA alerts snapshot (if present)
    """
    for result in report_data.results:
        scenario_dir = output_dir / result.name
        scenario_dir.mkdir(parents=True, exist_ok=True)

        json_result = result.model_dump(mode="json")
        steps_dicts = _steps_to_dicts(result.steps)

        # Flight declarations
        if json_result.get("flight_declaration_data"):
            _write_json(scenario_dir, "flight_declaration.json", json_result["flight_declaration_data"])

        declarations_list = json_result.get("flight_declarations_data")
        if not isinstance(declarations_list, list) or not declarations_list:
            declarations_list = try_load_declarations_for_scenario(result.name)
        if isinstance(declarations_list, list):
            for idx, decl in enumerate(declarations_list):
                _write_json(scenario_dir, f"flight_declaration_{idx}.json", decl)

        # Telemetry (primary / combined)
        if json_result.get("telemetry_data"):
            _write_json(scenario_dir, "telemetry.json", json_result["telemetry_data"])

        # Per-ownship telemetry from Generate Telemetry steps
        _save_per_ownship_telemetry(steps_dicts, scenario_dir)

        # Air traffic
        if json_result.get("air_traffic_data"):
            _write_json(scenario_dir, "air_traffic.json", json_result["air_traffic_data"])

        # DAA incident logs
        incident_logs = extract_step_payload(steps_dicts, "get_daa_incident_logs", "Get DAA Incident Logs")
        if isinstance(incident_logs, list) and incident_logs:
            _write_json(scenario_dir, "incident_logs.json", incident_logs)

        # DAA active alerts snapshot
        active_alerts = extract_step_payload(steps_dicts, "get_daa_active_alerts", "Get Active DAA Alerts")
        if isinstance(active_alerts, list) and active_alerts:
            _write_json(scenario_dir, "active_alerts.json", active_alerts)
