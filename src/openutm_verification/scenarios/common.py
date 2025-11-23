import json
from functools import partial
from pathlib import Path
from typing import Any, List, cast

from loguru import logger

from openutm_verification.core.clients.air_traffic.air_traffic_client import (
    AirTrafficClient,
)
from openutm_verification.core.clients.flight_blender.flight_blender_client import (
    FlightBlenderClient,
)
from openutm_verification.core.clients.opensky.opensky_client import OpenSkyClient
from openutm_verification.core.execution.config_models import config
from openutm_verification.core.reporting.reporting_models import (
    ScenarioResult,
    Status,
    StepResult,
)
from openutm_verification.simulator.flight_declaration import FlightDeclarationGenerator
from openutm_verification.simulator.geo_json_telemetry import GeoJSONFlightsSimulator
from openutm_verification.simulator.models.flight_data_types import (
    GeoJSONFlightsSimulatorConfiguration,
)

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


def _run_submit_airtraffic_flow(steps: list[partial[Any]]) -> List[StepResult]:
    """Execute OpenSky flow steps returning the list of StepResults."""

    def _execute_step(step_func: partial[Any], current_observations: Any | None) -> tuple[StepResult, Any | None]:
        name = _callable_name(step_func)
        # Submit step consumes observations
        if "submit_air_traffic" in name:
            if current_observations:
                return (
                    step_func(observations=current_observations),
                    current_observations,
                )
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
        if "fetch" in name or "generate" in name:
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


def run_sdsp_scenario_template(
    scenario_id: str,
    *,
    fb_client: FlightBlenderClient | None = None,
    steps: list[partial[Any]],
) -> ScenarioResult:
    step_results: List[StepResult] = []

    for step_func in steps:
        logger.debug(f"Executing step: {step_func}")
        params = step_func.keywords
        logger.debug(f"Parameters in the step: {params}")
        step_result: StepResult = step_func()
        step_results.append(step_result)
        logger.debug(f"Step result: {step_result}")

    for result in step_results:
        if type(result) is not StepResult:
            logger.error(f"Invalid step result type: {type(result)}")
            # print(result)
    final_status = Status.PASS if all(s.status == Status.PASS for s in step_results) else Status.FAIL
    total_duration = sum(s.duration for s in step_results)

    return ScenarioResult(
        name=scenario_id,
        status=final_status,
        duration_seconds=total_duration,
        steps=step_results,
    )


def run_air_traffic_scenario_template(
    scenario_id: str,
    *,
    fb_client: FlightBlenderClient | None = None,
    air_traffic_client: AirTrafficClient | None = None,
    steps: list[partial[Any]],
) -> ScenarioResult:
    step_results: List[StepResult] = []

    single_or_multiple_sensors = config.air_traffic_simulator_settings.single_or_multiple_sensors

    def _execute_step(step_func: partial[Any], current_observations: Any | None) -> tuple[StepResult, Any | None]:
        name = _callable_name(step_func)
        # Submit step consumes observations
        if "submit_simulated_air_traffic" in name:
            if current_observations:
                return (
                    step_func(
                        observations=current_observations,
                        single_or_multiple_sensors=single_or_multiple_sensors,
                    ),
                    current_observations,
                )
            return (
                StepResult(
                    name="Submit Simulated Air Traffic (skipped)",
                    status=Status.PASS,
                    duration=0.0,
                    details="No observations to submit",
                ),
                current_observations,
            )

        res: StepResult = step_func()
        if "fetch" in name or "generate" in name:
            res, observations = _redact_fetch_details(res)
            return res, observations
        return res, current_observations

    step_results: List[StepResult] = []
    if air_traffic_client is not None and fb_client is not None:
        observations: Any | None = None
        for step in steps:
            step_result, observations = _execute_step(step, observations)
            step_results.append(step_result)
            if step_result.status == Status.FAIL:
                break

    final_status = Status.PASS if all(s.status == Status.PASS for s in step_results) else Status.FAIL
    total_duration = sum(s.duration for s in step_results)

    return ScenarioResult(
        name=scenario_id,
        status=final_status,
        duration_seconds=total_duration,
        steps=step_results,
    )


def run_scenario_template(
    scenario_id: str,
    *,
    fb_client: FlightBlenderClient | None = None,
    air_traffic_client: AirTrafficClient | None = None,
    opensky_client: OpenSkyClient | None = None,
    steps: list[partial[Any]],
    duration: int = DEFAULT_TELEMETRY_DURATION,
) -> ScenarioResult:
    """Unified scenario runner supporting multiple client combinations.

    Supported flows:
    1. Declaration flow: fb_client only (generates flight declaration + telemetry)
    2. OpenSky flow: fb_client + opensky_client (fetches live data)
    3. Air traffic simulation: fb_client + air_traffic_client (generates simulated data)
    4. Declaration + OpenSky: fb_client + opensky_client (declaration flow)
    5. Declaration + Air traffic: fb_client + air_traffic_client (declaration flow)
    """

    # Log which clients are active
    active_clients = []
    if fb_client:
        active_clients.append(f"FB={fb_client.__class__.__name__}")
    if opensky_client:
        active_clients.append(f"OpenSky={opensky_client.__class__.__name__}")
    if air_traffic_client:
        active_clients.append(f"AirTraffic={air_traffic_client.__class__.__name__}")

    logger.debug(f"Active clients for '{scenario_id}': {', '.join(active_clients) if active_clients else 'None'}")

    # Determine scenario type based on client combination
    is_declaration_flow = fb_client is not None and air_traffic_client is None and opensky_client is None
    is_opensky_flow = opensky_client is not None
    is_air_traffic_flow = air_traffic_client is not None

    # Only generate flight declaration/telemetry data for declaration flows
    flight_declaration = None
    telemetry_states = None

    if is_declaration_flow:
        # Get scenario-specific config paths, falling back to global defaults
        scenario_config = config.scenarios.get(scenario_id)
        if scenario_config is None:
            scenario_config = config.data_files

        telemetry_path = scenario_config.telemetry or config.data_files.telemetry
        flight_declaration_path = scenario_config.flight_declaration or config.data_files.flight_declaration

        if not telemetry_path or not flight_declaration_path:
            error_msg = (
                f"Declaration flow for '{scenario_id}' missing required config paths: "
                f"telemetry={telemetry_path}, flight_declaration={flight_declaration_path}"
            )
            logger.error(error_msg)
            return ScenarioResult(
                name=scenario_id,
                status=Status.FAIL,
                duration_seconds=0,
                steps=[],
                error_message="Missing configuration paths for data generation.",
            )

        try:
            flight_declaration = _generate_flight_declaration(flight_declaration_path)
            telemetry_states = _generate_telemetry(telemetry_path, duration=duration)
            logger.info(f"Generated flight declaration and {len(telemetry_states)} telemetry states")
        except Exception as e:
            logger.error(f"Failed to generate data for scenario '{scenario_id}': {e}")
            return ScenarioResult(
                name=scenario_id,
                status=Status.FAIL,
                duration_seconds=0,
                steps=[],
                error_message=f"Data generation failed: {e}",
            )

    # Route to appropriate flow based on client combination
    step_results: List[StepResult] = []

    if is_declaration_flow:
        # Standard declaration flow: upload -> steps -> teardown
        logger.debug(f"Running declaration flow for '{scenario_id}'")
        # Type narrowing: These are guaranteed non-None by is_declaration_flow logic
        assert fb_client is not None, "fb_client must be set for declaration flow"
        assert flight_declaration is not None, "flight_declaration must be generated for declaration flow"
        assert telemetry_states is not None, "telemetry_states must be generated for declaration flow"
        step_results = _run_declaration_flow(
            fb_client=fb_client,
            flight_declaration=flight_declaration,
            telemetry_states=telemetry_states,
            steps=steps,
        )
    elif is_opensky_flow or is_air_traffic_flow:
        # Data-fetching flows: fetch/generate -> submit
        flow_type = "OpenSky" if is_opensky_flow else "Air Traffic"
        logger.debug(f"Running {flow_type} submission flow for '{scenario_id}'")
        step_results = _run_submit_airtraffic_flow(steps)
    else:
        # No valid clients provided
        logger.error(f"Scenario '{scenario_id}' has no valid client configuration.")
        return ScenarioResult(
            name=scenario_id,
            status=Status.FAIL,
            duration_seconds=0,
            steps=[],
            error_message="No valid client configuration provided (need fb_client, opensky_client, or air_traffic_client).",
        )

    final_status = Status.PASS if all(s.status == Status.PASS for s in step_results) else Status.FAIL
    total_duration = sum(s.duration for s in step_results)

    return ScenarioResult(
        name=scenario_id,
        status=final_status,
        duration_seconds=total_duration,
        steps=step_results,
        flight_declaration_data=flight_declaration,
        telemetry_data=telemetry_states,
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
