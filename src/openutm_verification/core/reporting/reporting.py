from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

from openutm_verification.core.execution.config_models import ReportingConfig
from openutm_verification.core.reporting.reporting_models import ReportData
from openutm_verification.core.reporting.visualize_flight import visualize_flight_path_2d, visualize_flight_path_3d


def generate_reports(
    report_data: ReportData,
    reporting_config: ReportingConfig,
    base_filename: str,
):
    """
    Generates reports based on the provided configuration.
    """
    output_dir = Path(reporting_config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

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


def _generate_html_report(report_data: ReportData, output_dir: Path, base_filename: str):
    """
    Generates an HTML report from the collected scenario results using a Jinja2 template.

    Args:
        report_data: A Pydantic model containing all the data for the report.
        output_dir: The directory where the report will be saved.
        base_filename: The base name for the report file (without extension).
    """
    # Generate visualizations for scenarios with flight data
    _generate_visualizations(report_data, output_dir, base_filename)

    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(enabled_extensions=("html", "xml"), default_for_string=True, default=True),
    )
    env.filters["markdown"] = lambda text: markdown.markdown(text) if text else ""
    template = env.get_template("report_template.html")

    html_content = template.render(report_data=report_data)

    report_path = output_dir / f"{base_filename}.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return report_path


def _generate_scenario_visualizations(result, telemetry_data, declaration_data, output_dir: Path, base_filename: str):
    """
    Generates 2D and 3D visualizations for a single scenario.

    Args:
        result: ScenarioResult to update with visualization paths.
        telemetry_data: Loaded telemetry data.
        declaration_data: Loaded declaration data.
        output_dir: Directory to save visualizations.
        base_filename: Base filename for consistent naming.
    """
    # Convert models to dicts if necessary
    telemetry_data = telemetry_data.model_dump() if hasattr(telemetry_data, "model_dump") else telemetry_data
    declaration_data = declaration_data.model_dump() if hasattr(declaration_data, "model_dump") else declaration_data

    # Sanitize scenario name for filename
    sanitized_name = result.name.replace(" ", "_").replace("-", "_")

    # Generate 2D visualization
    vis_2d_filename = f"{base_filename}_{sanitized_name}_2d.html"
    vis_2d_path = output_dir / vis_2d_filename
    visualize_flight_path_2d(telemetry_data, declaration_data, str(vis_2d_path))
    result.visualization_2d_path = str(vis_2d_path.relative_to(output_dir))

    # Generate 3D visualization
    vis_3d_filename = f"{base_filename}_{sanitized_name}_3d.html"
    vis_3d_path = output_dir / vis_3d_filename
    visualize_flight_path_3d(telemetry_data, declaration_data, str(vis_3d_path))
    result.visualization_3d_path = str(vis_3d_path.relative_to(output_dir))


def _generate_visualizations(report_data: ReportData, output_dir: Path, base_filename: str):
    """
    Generates flight visualizations for scenarios that have flight data.

    Args:
        report_data: The report data containing scenario results.
        output_dir: The directory where visualizations will be saved.
        base_filename: The base filename used for consistent naming.
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
                _generate_scenario_visualizations(result, telemetry_data, declaration_data, output_dir, base_filename)
            except Exception as e:
                logger.warning(f"Failed to generate visualizations for scenario '{result.name}': {e}")
