"""
Core execution logic for running verification scenarios.
"""

import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import ValidationError

from openutm_verification.core.clients.air_traffic.base_client import (
    AirTrafficError,
)
from openutm_verification.core.clients.opensky.base_client import (
    OpenSkyError,
)
from openutm_verification.core.execution.config_models import AppConfig
from openutm_verification.core.execution.dependencies import scenarios
from openutm_verification.core.execution.dependency_resolution import CONTEXT, call_with_dependencies
from openutm_verification.core.reporting.reporting import generate_reports
from openutm_verification.core.reporting.reporting_models import (
    ReportData,
    ReportSummary,
    ScenarioResult,
    Status,
)
from openutm_verification.utils.paths import get_docs_directory


def _sanitize_config(data: Any) -> Any:
    """
    Recursively sanitize sensitive fields in the configuration data for logging and reporting.

    Masks client_id, client_secret, audience, and scopes anywhere in the data structure.
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


def run_verification_scenarios(config: AppConfig, config_path: Path):
    """
    Executes the verification scenarios based on the provided configuration.
    """
    run_timestamp = datetime.now(timezone.utc)
    start_time_utc = run_timestamp.isoformat()
    start_time_obj = run_timestamp

    logger.info("Starting verification run...")
    logger.info(f"Using configuration: {config_path}")

    # Sanitize config for logging and reporting
    sanitized_config_dict = _sanitize_config(config.model_dump())
    logger.debug(f"Configuration details:\n{json.dumps(sanitized_config_dict, indent=2)}")

    scenario_results = []
    for scenario_id, scenario_func in scenarios():
        try:
            result = call_with_dependencies(scenario_func)
        except (AirTrafficError, OpenSkyError, ValidationError) as e:
            logger.error(f"Failed to run scenario '{scenario_id}': {e}")
            result = ScenarioResult(
                name=scenario_id,
                status=Status.FAIL,
                duration_seconds=0,
                steps=[],
                error_message=str(e),
                docs=None,
            )
        result.docs = CONTEXT.get().get("docs")
        scenario_results.append(result)
        logger.info(f"Scenario {scenario_id} finished with status: {result.status}")

    end_time_obj = datetime.now(timezone.utc)
    end_time_utc = end_time_obj.isoformat()
    total_duration_seconds = (end_time_obj - start_time_obj).total_seconds()

    failed_scenarios = sum(1 for r in scenario_results if r.status == Status.FAIL)
    overall_status = Status.FAIL if failed_scenarios > 0 else Status.PASS

    docs_dir = get_docs_directory()

    report_data = ReportData(
        run_id=config.run_id,
        tool_version=version("openutm-verification"),
        start_time_utc=start_time_utc,
        end_time_utc=end_time_utc,
        total_duration_seconds=total_duration_seconds,
        overall_status=overall_status,
        flight_blender_url=config.flight_blender.url,
        deployment_details=config.reporting.deployment_details,
        config_file=str(config_path),
        config=sanitized_config_dict,  # Use sanitized config in the report
        results=scenario_results,
        summary=ReportSummary(
            total_scenarios=len(scenario_results),
            passed=sum(1 for r in scenario_results if r.status == Status.PASS),
            failed=failed_scenarios,
        ),
        docs_dir=str(docs_dir) if docs_dir else None,
    )

    logger.info(f"Verification run complete with overall status: {overall_status}")

    base_filename = f"report_{run_timestamp.strftime('%Y-%m-%dT%H-%M-%SZ')}"
    generate_reports(report_data, config.reporting, base_filename)
    return failed_scenarios
