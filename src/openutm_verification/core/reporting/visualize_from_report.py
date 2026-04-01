"""Generate report visualizations directly from a report.json artifact.

Delegates all visualization logic to the shared ``_viz_engine`` module.
This module handles only JSON parsing and the CLI entry point.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from loguru import logger

from openutm_verification.core.reporting._viz_engine import render_scenario_visualizations


def generate_visualizations_from_report(
    report_json_path: Path,
    output_dir: Path | None = None,
    scenario_name: str | None = None,
) -> list[Path]:
    """Generate 2D and 3D visualizations from report.json scenarios."""
    report_json_path = report_json_path.resolve()
    with report_json_path.open("r", encoding="utf-8") as report_file:
        report = json.load(report_file)

    results = report.get("results", [])
    if not isinstance(results, list):
        raise ValueError("Invalid report.json: `results` must be a list")

    base_output_dir = output_dir.resolve() if output_dir else report_json_path.parent.resolve()
    generated_files: list[Path] = []

    for result in results:
        if not isinstance(result, dict):
            continue

        name = str(result.get("name") or "scenario")
        if scenario_name and name != scenario_name:
            continue

        telemetry_data = result.get("telemetry_data")
        declaration_data = result.get("flight_declaration_data")
        if not isinstance(telemetry_data, list) or not isinstance(declaration_data, dict):
            logger.warning(f"Skipping scenario '{name}': missing telemetry/declaration in report artifact")
            continue

        raw_steps = result.get("steps")
        steps: list[dict[str, Any]] = []
        if isinstance(raw_steps, list):
            steps = [step for step in raw_steps if isinstance(step, dict)]

        vis_2d, vis_3d = render_scenario_visualizations(
            scenario_name=name,
            steps=steps,
            telemetry_data=telemetry_data,
            declaration_data=declaration_data,
            output_dir=base_output_dir,
            air_traffic_data=result.get("air_traffic_data"),
            flight_declarations_data=result.get("flight_declarations_data"),
            filename_prefix="from_report",
        )

        generated_files.extend([vis_2d, vis_3d])

    return generated_files


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate visualizations from report.json")
    parser.add_argument("report_json", type=Path, help="Path to report.json")
    parser.add_argument("--output-dir", type=Path, default=None, help="Optional output directory")
    parser.add_argument("--scenario", type=str, default=None, help="Optional scenario name filter")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    outputs = generate_visualizations_from_report(
        report_json_path=args.report_json,
        output_dir=args.output_dir,
        scenario_name=args.scenario,
    )

    if not outputs:
        logger.warning("No visualizations were generated")
        return

    for output in outputs:
        logger.info(f"Generated: {output}")


if __name__ == "__main__":
    main()
