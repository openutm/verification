"""
Core execution logic for running verification scenarios.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

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
from openutm_verification.core.execution.dependency_resolution import CONTEXT
from openutm_verification.core.execution.scenario_loader import load_yaml_scenario_definition
from openutm_verification.core.reporting.reporting import _sanitize_config, create_report_data, generate_reports
from openutm_verification.core.reporting.reporting_models import (
    ScenarioResult,
    Status,
)
from openutm_verification.utils.paths import get_docs_directory

if TYPE_CHECKING:
    from openutm_verification.server.runner import SessionManager


async def run_verification_scenarios(config: AppConfig, config_path: Path, session_manager: "SessionManager | None" = None):
    """
    Executes the verification scenarios based on the provided configuration.
    """

    start_time = datetime.now(timezone.utc)

    logger.info("Starting verification run...")
    logger.info(f"Using configuration: {config_path}")

    # Sanitize config for logging and reporting
    sanitized_config_dict = _sanitize_config(config.model_dump())
    logger.debug(f"Configuration details:\n{json.dumps(sanitized_config_dict, indent=2)}")

    # Initialize SessionManager
    if session_manager is None:
        from openutm_verification.server.runner import SessionManager as RunnerSessionManager

        session_manager = RunnerSessionManager(config_path=str(config_path))

    scenario_results = []
    for scenario_id in scenarios():
        try:
            # Initialize session with the current context
            await session_manager.initialize_session()

            scenario_def = load_yaml_scenario_definition(scenario_id)
            await session_manager.run_scenario(scenario_def)
            state = session_manager.session_context.state if session_manager.session_context else None
            steps = state.steps if state else []
            failed = any(s.status == Status.FAIL for s in steps)
            status = Status.FAIL if failed else Status.PASS
            result = ScenarioResult(
                name=scenario_id,
                status=status,
                duration=0,
                steps=steps,
                flight_declaration_data=state.flight_declaration_data if state else None,
                flight_declaration_via_operational_intent_data=state.flight_declaration_via_operational_intent_data if state else None,
                telemetry_data=state.telemetry_data if state else None,
                air_traffic_data=state.air_traffic_data if state else [],
            )
        except (AirTrafficError, OpenSkyError, ValidationError) as e:
            logger.error(f"Failed to run scenario '{scenario_id}': {e}")
            result = ScenarioResult(
                name=scenario_id,
                status=Status.FAIL,
                duration=0,
                steps=[],
                error_message=str(e),
                docs=None,
            )
        finally:
            # Ensure session is closed after each scenario to clean up resources
            await session_manager.close_session()

        # Enrich result with context data
        context_data = CONTEXT.get()
        result.suite_name = context_data.get("suite_name")
        result.docs = context_data.get("docs")

        scenario_results.append(result)
        logger.info(f"Scenario {scenario_id} finished with status: {result.status}")

    end_time_obj = datetime.now(timezone.utc)

    docs_dir = get_docs_directory()
    report_data = create_report_data(
        config=config,
        config_path=str(config_path),
        results=scenario_results,
        start_time=start_time,
        end_time=end_time_obj,
        docs_dir=str(docs_dir) if docs_dir else None,
    )

    logger.info(f"Verification run complete with overall status: {report_data.overall_status}")

    generate_reports(report_data, config.reporting)
    return report_data.summary.failed
