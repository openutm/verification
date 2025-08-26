"""
This module contains the core logic for running verification scenarios.
"""

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from openutm_verification.client import NoAuthCredentialsGetter, PassportCredentialsGetter
from openutm_verification.config_models import AppConfig, ReportData, ReportSummary, Status
from openutm_verification.flight_blender_client import FlightBlenderClient
from openutm_verification.reporting import generate_reports
from tests.scenarios.registry import SCENARIO_REGISTRY


def _get_auth_provider(auth_config):
    """Returns the appropriate authentication provider based on config."""
    if auth_config.type == "passport":
        return NoAuthCredentialsGetter()
        # IGNORE FOR NOW
        # return PassportCredentialsGetter(
        #     client_id=auth_config.client_id,
        #     client_secret=auth_config.client_secret,
        #     audience=auth_config.audience,
        #     token_url=auth_config.token_url,
        # )
    return NoAuthCredentialsGetter()


def run_verification_scenarios(config: AppConfig, config_path: Path):
    """
    Executes the verification scenarios based on the provided configuration.
    """
    run_timestamp = datetime.now(timezone.utc)
    start_time_utc = run_timestamp.isoformat()
    start_time_obj = run_timestamp

    logger.info("Starting verification run...")
    logger.info(f"Using configuration: {config_path}")
    logger.debug(f"Configuration details: {config.model_dump_json(indent=2)}")

    auth_provider = _get_auth_provider(config.flight_blender.auth)
    credentials = auth_provider.get_cached_credentials(audience="testflight.flightblender.com", scopes=["flightblender.write"])

    with FlightBlenderClient(
        base_url=config.flight_blender.url,
        credentials=credentials,
    ) as client:
        scenarios_to_run = config.scenarios
        scenario_results = []
        if scenarios_to_run:
            logger.info(f"Found {len(scenarios_to_run)} scenarios to run.")
            for scenario_id in scenarios_to_run:
                if scenario_id in SCENARIO_REGISTRY:
                    logger.info("=" * 100)
                    logger.info(f"Running scenario: {scenario_id}")
                    scenario_func = SCENARIO_REGISTRY[scenario_id]
                    result = scenario_func(client, scenario_id)
                    scenario_results.append(result)
                    logger.info(f"Scenario {scenario_id} finished with status: {result.status}")
                else:
                    logger.warning(f"Scenario '{scenario_id}' not found in registry.")
            logger.info("=" * 100)
        else:
            logger.warning("No scenarios found in the configuration.")

    end_time_obj = datetime.now(timezone.utc)
    end_time_utc = end_time_obj.isoformat()
    total_duration_seconds = (end_time_obj - start_time_obj).total_seconds()

    failed_scenarios = sum(1 for r in scenario_results if r.status == Status.FAIL)
    overall_status = Status.FAIL if failed_scenarios > 0 else Status.PASS

    report_data = ReportData(
        run_id=start_time_utc,
        tool_version="1.0.0",
        start_time_utc=start_time_utc,
        end_time_utc=end_time_utc,
        total_duration_seconds=total_duration_seconds,
        overall_status=overall_status,
        flight_blender_url=config.flight_blender.url,
        deployment_details=config.reporting.deployment_details,
        config_file=str(config_path),
        config=config.model_dump(),
        results=scenario_results,
        summary=ReportSummary(
            total_scenarios=len(scenario_results),
            passed=sum(1 for r in scenario_results if r.status == Status.PASS),
            failed=failed_scenarios,
        ),
    )

    base_filename = f"report_{run_timestamp.strftime('%Y-%m-%dT%H-%M-%SZ')}"
    generate_reports(report_data, config.reporting, base_filename)

    logger.info("Verification run complete.")
