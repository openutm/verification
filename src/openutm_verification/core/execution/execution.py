"""
Core execution logic for running verification scenarios.
"""

import importlib
import json
import pkgutil
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from pydantic import ValidationError

import openutm_verification.scenarios
from openutm_verification.core.clients.air_traffic.base_client import (
    AirTrafficError,
)
from openutm_verification.core.clients.opensky.base_client import (
    OpenSkyError,
)
from openutm_verification.core.execution.config_models import AppConfig
from openutm_verification.core.execution.dependencies import scenarios
from openutm_verification.core.execution.dependency_resolution import CONTEXT, call_with_dependencies
from openutm_verification.core.execution.scenario_loader import load_yaml_scenario_definition
from openutm_verification.core.reporting.reporting import _sanitize_config, create_report_data, generate_reports
from openutm_verification.core.reporting.reporting_models import (
    ScenarioResult,
    Status,
)
from openutm_verification.scenarios.registry import SCENARIO_REGISTRY
from openutm_verification.utils.paths import get_docs_directory


def _import_python_scenarios():
    """Import all python scenarios to populate the registry."""
    path = list(openutm_verification.scenarios.__path__)
    prefix = openutm_verification.scenarios.__name__ + "."

    for _, name, _ in pkgutil.iter_modules(path, prefix):
        try:
            importlib.import_module(name)
        except Exception as e:
            logger.warning(f"Failed to import scenario module {name}: {e}")


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

    # Import Python scenarios to populate registry
    _import_python_scenarios()

    scenario_results = []
    for scenario_id in scenarios():
        try:
            # Initialize session with the current context
            await session_manager.initialize_session()

            if scenario_id in SCENARIO_REGISTRY:
                logger.info(f"Running Python scenario: {scenario_id}")
                wrapper = SCENARIO_REGISTRY[scenario_id]["func"]
                # Unwrap to get the original function for dependency injection
                func_to_call = getattr(wrapper, "__wrapped__", wrapper)

                # Execute within the session context
                # session_manager.initialize_session() already sets up session_context but doesn't enter it
                # We need to manually enter the context or use run_scenario logic
                # session_context is a ScenarioContext.
                # ScenarioContext.__enter__ sets the thread-local state.

                if not session_manager.session_context:
                    raise RuntimeError("Session context not initialized")

                with session_manager.session_context:
                    await call_with_dependencies(func_to_call, resolver=session_manager.session_resolver)

            else:
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
