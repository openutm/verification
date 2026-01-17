import json
import shutil
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any, TypeVar

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

from openutm_verification.core.execution.config_models import AppConfig, ReportingConfig
from openutm_verification.core.reporting.reporting_models import (
    ReportData,
    ReportSummary,
    ScenarioResult,
    Status,
)
from openutm_verification.core.reporting.visualize_flight import visualize_flight_path_2d, visualize_flight_path_3d
from openutm_verification.utils.time_utils import get_run_timestamp_str

T = TypeVar("T")


def _sanitize_config(data: Any) -> Any:
    """
    Recursively sanitize sensitive fields in the configuration data.
    """
    sensitive_mask = "***MASKED***"
    sensitive_keys = ["client_id", "client_secret", "audience", "scopes"]

    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if key in sensitive_keys:
                sanitized[key] = sensitive_mask
            else:
                sanitized[key] = _sanitize_config(value)
        return sanitized
    elif isinstance(data, list):
        return [_sanitize_config(item) for item in data]
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
    output_dir = Path(reporting_config.output_dir) / get_run_timestamp_str(report_data.start_time)
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
    template = env.get_template("report_template.html")

    html_content = template.render(report_data=report_data.model_dump(mode="json"))

    report_path = output_dir / f"{base_filename}.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return report_path


def _generate_scenario_visualizations(result: ScenarioResult, output_dir: Path):
    """
    Generates 2D and 3D visualizations for a single scenario.

    Args:
        result: ScenarioResult to update with visualization paths.
        telemetry_data: Loaded telemetry data.
        declaration_data: Loaded declaration data.
        output_dir: Directory to save visualizations.
    """
    if result.flight_declaration_data is None or result.telemetry_data is None:
        return

    flight_declaration_dict = result.flight_declaration_data.model_dump()

    # Create scenario directory
    scenario_dir = output_dir / result.name
    scenario_dir.mkdir(parents=True, exist_ok=True)

    # Generate 2D visualization
    vis_2d_filename = "visualization_2d.html"
    vis_2d_path = scenario_dir / vis_2d_filename
    visualize_flight_path_2d(result.telemetry_data, flight_declaration_dict, vis_2d_path)
    result.visualization_2d_path = str(vis_2d_path.relative_to(output_dir))

    # Generate 3D visualization
    vis_3d_filename = "visualization_3d.html"
    vis_3d_path = scenario_dir / vis_3d_filename
    visualize_flight_path_3d(result.telemetry_data, flight_declaration_dict, vis_3d_path)
    result.visualization_3d_path = str(vis_3d_path.relative_to(output_dir))


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


def _save_scenario_data(report_data: ReportData, output_dir: Path):
    """
    Saves generated data for each scenario in a subdirectory.
    """
    for result in report_data.results:
        scenario_dir = output_dir / result.name
        scenario_dir.mkdir(parents=True, exist_ok=True)

        json_result = result.model_dump(mode="json")

        if json_result.get("flight_declaration_data"):
            file_path = scenario_dir / "flight_declaration.json"
            file_path.write_text(json.dumps(json_result["flight_declaration_data"], indent=2), encoding="utf-8")
            logger.debug(f"Saved flight declaration data to {file_path}")

        if json_result.get("telemetry_data"):
            file_path = scenario_dir / "telemetry.json"
            file_path.write_text(json.dumps(json_result["telemetry_data"], indent=2), encoding="utf-8")
            logger.debug(f"Saved telemetry data to {file_path}")

        if json_result.get("air_traffic_data"):
            file_path = scenario_dir / "air_traffic.json"
            file_path.write_text(json.dumps(json_result["air_traffic_data"], indent=2), encoding="utf-8")
            logger.debug(f"Saved air traffic data to {file_path}")
