"""
Core execution logic for running verification scenarios.
"""

import inspect
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import ValidationError

from openutm_verification.auth import get_auth_provider
from openutm_verification.core.clients.air_traffic.air_traffic_client import (
    AirTrafficClient,
)
from openutm_verification.core.clients.air_traffic.base_client import (
    AirTrafficError,
    create_air_traffic_settings,
)
from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.clients.opensky.base_client import (
    OpenSkyError,
    create_opensky_settings,
)
from openutm_verification.core.clients.opensky.opensky_client import OpenSkyClient
from openutm_verification.core.execution.config_models import AppConfig
from openutm_verification.core.reporting.reporting import generate_reports
from openutm_verification.core.reporting.reporting_models import (
    ReportData,
    ReportSummary,
    ScenarioResult,
    Status,
)
from openutm_verification.scenarios.registry import SCENARIO_REGISTRY


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

    auth_provider = get_auth_provider(config.flight_blender.auth)
    credentials = auth_provider.get_cached_credentials(
        audience=config.flight_blender.auth.audience or "",
        scopes=config.flight_blender.auth.scopes or [],
    )

    with FlightBlenderClient(base_url=config.flight_blender.url, credentials=credentials) as fb_client:
        scenarios_to_run = config.scenarios
        scenario_results = []
        logger.info(f"Found {len(scenarios_to_run)} scenarios to run.")
        for scenario_id in scenarios_to_run:
            if scenario_id in SCENARIO_REGISTRY:
                logger.info("=" * 100)
                logger.info(f"Running scenario: {scenario_id}")
                scenario_func = SCENARIO_REGISTRY[scenario_id]
                # Detect if the scenario expects an OpenSky client or AirTraffic client as an argument
                params = list(inspect.signature(scenario_func).parameters.keys())

                if "opensky_client" in params:
                    try:
                        settings = create_opensky_settings()
                        with OpenSkyClient(settings) as opensky_client:
                            result = scenario_func(fb_client, opensky_client, scenario_id)
                    except (OpenSkyError, ValidationError) as e:
                        logger.error(f"Failed to run OpenSky-enabled scenario '{scenario_id}': {e}")
                        result = ScenarioResult(
                            name=scenario_id,
                            status=Status.FAIL,
                            duration_seconds=0,
                            steps=[],
                            error_message=str(e),
                        )
                elif "air_traffic_client" in params:
                    try:
                        settings = create_air_traffic_settings()
                        with AirTrafficClient(settings) as air_traffic_client:
                            result = scenario_func(fb_client, air_traffic_client, scenario_id)
                    except (AirTrafficError, ValidationError) as e:
                        logger.error(f"Failed to run AirTraffic-enabled scenario '{scenario_id}': {e}")
                        result = ScenarioResult(
                            name=scenario_id,
                            status=Status.FAIL,
                            duration_seconds=0,
                            steps=[],
                            error_message=str(e),
                        )
                else:
                    result = scenario_func(fb_client, scenario_id)
                scenario_results.append(result)
                logger.info(f"Scenario {scenario_id} finished with status: {result.status}")
            else:
                logger.warning(f"Scenario '{scenario_id}' not found in registry.")
        logger.info("=" * 100)

    end_time_obj = datetime.now(timezone.utc)
    end_time_utc = end_time_obj.isoformat()
    total_duration_seconds = (end_time_obj - start_time_obj).total_seconds()

    failed_scenarios = sum(1 for r in scenario_results if r.status == Status.FAIL)
    overall_status = Status.FAIL if failed_scenarios > 0 else Status.PASS

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
    )

    logger.info(f"Verification run complete with overall status: {overall_status}")

    base_filename = f"report_{run_timestamp.strftime('%Y-%m-%dT%H-%M-%SZ')}"
    generate_reports(report_data, config.reporting, base_filename)
