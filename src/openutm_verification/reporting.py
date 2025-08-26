import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

from .config_models import ReportData, ReportingConfig


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
    with open(report_path, "w") as f:
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
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(enabled_extensions=("html", "xml"), default_for_string=True, default=True),
    )
    template = env.get_template("report_template.html")

    html_content = template.render(report_data=report_data)

    report_path = output_dir / f"{base_filename}.html"
    with open(report_path, "w") as f:
        f.write(html_content)
    return report_path
