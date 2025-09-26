import json
from functools import partial
from pathlib import Path
from typing import Any, List, cast
from unittest.mock import DEFAULT

from loguru import logger

from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.clients.opensky.opensky_client import OpenSkyClient
from openutm_verification.core.execution.config_models import config
from openutm_verification.core.reporting.reporting_models import ScenarioResult, Status, StepResult
from openutm_verification.simulator.flight_declaration import FlightDeclarationGenerator
from openutm_verification.simulator.geo_json_telemetry import GeoJSONFlightsSimulator
from openutm_verification.simulator.models.flight_data_types import GeoJSONFlightsSimulatorConfiguration

DEFAULT_TELEMETRY_DURATION = 30  # seconds


def _callable_name(func_like: Any) -> str:
    """Best-effort name extraction for partials or callables."""
    target = getattr(func_like, "func", func_like)
    return getattr(target, "__name__", "<step>")


def _redact_fetch_details(res: StepResult) -> tuple[StepResult, Any | None]:
    """Normalize fetch result details to only include count and extract observations.

    Returns the possibly-modified StepResult and the extracted observations (or None).
    """
    if res.status != Status.PASS:
        return res, None

    details = res.details
    observations: Any | None = None
    if isinstance(details, dict) and "observations" in details:
        observations = details.get("observations")
        try:
            res.details = {"count": len(observations or [])}
        except TypeError:
            res.details = {"count": 0}
    elif isinstance(details, list):
        observations = details
        res.details = {"count": len(details)}
    else:
        res.details = {"count": 0}
        observations = None
    return res, observations


def _run_opensky_flow(steps: list[partial[Any]]) -> List[StepResult]:
    """Execute OpenSky flow steps returning the list of StepResults."""

    def _execute_step(step_func: partial[Any], current_observations: Any | None) -> tuple[StepResult, Any | None]:
        name = _callable_name(step_func)
        # Submit step consumes observations
        if "submit_air_traffic" in name:
            if current_observations:
                return step_func(observations=current_observations), current_observations
            return (
                StepResult(
                    name="Submit Air Traffic (skipped)",
                    status=Status.PASS,
                    duration=0.0,
                    details="No observations to submit",
                ),
                current_observations,
            )

        # Generic execution (fetch steps usually have opensky_client already bound via partial)
        res: StepResult = step_func()
        if "fetch" in name:
            res, observations = _redact_fetch_details(res)
            return res, observations
        return res, current_observations

    results: List[StepResult] = []
    observations: Any | None = None
    for step in steps:
        step_result, observations = _execute_step(step, observations)
        results.append(step_result)
        if step_result.status == Status.FAIL:
            break
    return results


def _run_declaration_flow(
    fb_client: FlightBlenderClient,
    flight_declaration: Any,
    telemetry_states: List[Any],
    steps: list[partial[Any]],
) -> List[StepResult]:
    """Execute standard declaration + steps + teardown using generated data and return StepResults."""
    upload_result = cast(StepResult, fb_client.upload_flight_declaration(flight_declaration))
    if upload_result.status == Status.FAIL or upload_result.details is None:
        # Return early with failure
        return [upload_result]

    operation_id = upload_result.details["id"]

    all_steps: List[StepResult] = [upload_result]
    for step_func in steps:
        kwargs = {}
        if "submit_telemetry" in _callable_name(step_func):
            kwargs["states"] = telemetry_states
        elif "submit_telemetry_from_file" in _callable_name(step_func):
            # TODO: read from file
            kwargs["states"] = telemetry_states
        step_result: StepResult = step_func(operation_id, **kwargs)
        all_steps.append(step_result)
        if step_result.status == Status.FAIL:
            break

    teardown_result: StepResult = cast(StepResult, fb_client.delete_flight_declaration(operation_id))
    all_steps.append(teardown_result)
    return all_steps


def _generate_flight_declaration(config_path: str) -> Any:
    """Generate a flight declaration from the config file at the given path."""
    try:
        generator = FlightDeclarationGenerator(bounds_path=Path(config_path))
        return generator.generate()
    except Exception as e:
        logger.error(f"Failed to generate flight declaration from {config_path}: {e}")
        raise


def _generate_telemetry(config_path: str, duration: int = DEFAULT_TELEMETRY_DURATION) -> List[Any]:
    """Generate telemetry states from the GeoJSON config file at the given path."""
    try:
        logger.debug(f"Generating telemetry states from {config_path} for duration {duration} seconds")
        with open(config_path, "r", encoding="utf-8") as f:
            geojson_data = json.load(f)

        simulator_config = GeoJSONFlightsSimulatorConfiguration(geojson=geojson_data)
        simulator = GeoJSONFlightsSimulator(simulator_config)

        simulator.generate_flight_grid_and_path_points(altitude_of_ground_level_wgs_84=570)
        return simulator.generate_states(duration=duration)
    except Exception as e:
        logger.error(f"Failed to generate telemetry states from {config_path}: {e}")
        raise


def run_scenario_template(
    scenario_name: str,
    *,
    fb_client: FlightBlenderClient | None = None,
    opensky_client: OpenSkyClient | None = None,
    steps: list[partial[Any]],
    duration: int = DEFAULT_TELEMETRY_DURATION,
) -> ScenarioResult:
    """Unified scenario runner supporting declaration and OpenSky flows.

    For declaration flows: Generates flight declaration and telemetry data in-memory from config.
    For OpenSky flows: Uses provided opensky_client to fetch live data.
    """
    # Get scenario-specific config paths, falling back to global defaults
    scenario_config = config.scenarios.get(scenario_name)
    if scenario_config is None:
        scenario_config = config.data_files

    telemetry_path = scenario_config.telemetry or config.data_files.telemetry
    flight_declaration_path = scenario_config.flight_declaration or config.data_files.flight_declaration

    if not telemetry_path or not flight_declaration_path:
        error_msg = (
            f"Scenario '{scenario_name}' missing required config paths: telemetry={telemetry_path}, flight_declaration={flight_declaration_path}"
        )
        logger.error(error_msg)
        return ScenarioResult(
            name=scenario_name,
            status=Status.FAIL,
            duration_seconds=0,
            steps=[],
            error_message="Missing configuration paths for data generation.",
        )

    # Generate data in-memory
    try:
        flight_declaration = _generate_flight_declaration(flight_declaration_path)
        telemetry_states = _generate_telemetry(telemetry_path, duration=duration)
        logger.info(f"Generated {len(telemetry_states)} telemetry states")
    except Exception as e:
        logger.error(f"Failed to generate data for scenario '{scenario_name}': {e}")
        return ScenarioResult(
            name=scenario_name,
            status=Status.FAIL,
            duration_seconds=0,
            steps=[],
            error_message=f"Data generation failed: {e}",
        )

    if fb_client or opensky_client:
        logger.debug(
            f"Running scenario '{scenario_name}' with FB={getattr(fb_client, '__class__', type('x', (), {})).__name__ if fb_client else 'None'}, "
            f"OS={getattr(opensky_client, '__class__', type('x', (), {})).__name__ if opensky_client else 'None'}"
        )

    if fb_client is not None and opensky_client is None:
        # Run declaration flow with generated data
        step_results = _run_declaration_flow(
            fb_client=fb_client,
            flight_declaration=flight_declaration,
            telemetry_states=telemetry_states,
            steps=steps,
        )
    elif fb_client is not None and opensky_client is not None:
        # OpenSky flow - requires both clients
        step_results = _run_opensky_flow(steps)
    else:
        logger.error(f"Scenario '{scenario_name}' is not supported.")
        return ScenarioResult(
            name=scenario_name,
            status=Status.FAIL,
            duration_seconds=0,
            steps=[],
            error_message="Unsupported scenario configuration.",
        )

    final_status = Status.PASS if all(s.status == Status.PASS for s in step_results) else Status.FAIL
    total_duration = sum(s.duration for s in step_results)

    return ScenarioResult(
        name=scenario_name,
        status=final_status,
        duration_seconds=total_duration,
        steps=step_results,
    )


def get_telemetry_path(telemetry_filename: str) -> str:
    """Helper to get the full path to a telemetry file."""
    parent_dir = Path(__file__).parent.resolve()
    return str(parent_dir / f"../assets/rid_samples/{telemetry_filename}")


def get_flight_declaration_path(flight_declaration_filename: str) -> str:
    """Helper to get the full path to a flight declaration file."""
    parent_dir = Path(__file__).parent.resolve()
    return str(parent_dir / f"../assets/flight_declarations_samples/{flight_declaration_filename}")


def get_geo_fence_path(geo_fence_filename: str) -> str:
    """Helper to get the full path to a geo-fence file."""
    parent_dir = Path(__file__).parent.resolve()
    return str(parent_dir / f"../assets/aoi_geo_fence_samples/{geo_fence_filename}")
