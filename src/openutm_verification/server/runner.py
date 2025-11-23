import inspect
import json
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Dict, List, Type, cast

import yaml
from loguru import logger
from pydantic import BaseModel

# Import dependencies to ensure decorators run
import openutm_verification.core.execution.dependencies  # noqa: F401
from openutm_verification.core.clients.air_traffic.air_traffic_client import AirTrafficClient
from openutm_verification.core.clients.flight_blender.flight_blender_client import FlightBlenderClient
from openutm_verification.core.clients.opensky.opensky_client import OpenSkyClient
from openutm_verification.core.execution.config_models import AppConfig, ConfigProxy
from openutm_verification.core.execution.dependency_resolution import DependencyResolver
from openutm_verification.core.reporting.reporting_models import Status, StepResult
from openutm_verification.models import OperationState
from openutm_verification.simulator.flight_declaration import FlightDeclarationGenerator
from openutm_verification.simulator.geo_json_telemetry import GeoJSONFlightsSimulator
from openutm_verification.simulator.models.flight_data_types import GeoJSONFlightsSimulatorConfiguration


class StepDefinition(BaseModel):
    id: str | None = None
    className: str
    functionName: str
    parameters: Dict[str, Any]


class ScenarioDefinition(BaseModel):
    steps: List[StepDefinition]


class DynamicRunner:
    def __init__(self, config_path: str = "config/default.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.client_map: Dict[str, Type] = {
            "FlightBlenderClient": FlightBlenderClient,
            "OpenSkyClient": OpenSkyClient,
            "AirTrafficClient": AirTrafficClient,
        }

    def _load_config(self) -> AppConfig:
        if not self.config_path.exists():
            # Try to find it relative to project root if we are in src/...
            pass

        # Fallback to absolute path if needed, but for now assume running from root
        with open(self.config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)

        config = AppConfig.model_validate(config_data)
        project_root = self.config_path.parent.parent
        config.resolve_paths(project_root)

        # Only initialize ConfigProxy if it hasn't been initialized yet
        try:
            ConfigProxy.initialize(config)
        except TypeError:
            # If already initialized, we can optionally override it or just ignore
            # For now, let's override to ensure we have the latest config
            ConfigProxy.override(config)

        return config

    def _generate_data(self):
        # Hardcoded for now, could be parameterized
        config_path = Path("config/bern/flight_declaration.json")

        # Generate Flight Declaration
        generator = FlightDeclarationGenerator(bounds_path=config_path)
        flight_declaration = generator.generate()

        # Generate Telemetry
        with open(config_path, "r", encoding="utf-8") as f:
            bounds = json.load(f)

        # Create a simple LineString feature from min/min to max/max
        flight_path_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "LineString", "coordinates": [[bounds["minx"], bounds["miny"]], [bounds["maxx"], bounds["maxy"]]]},
                }
            ],
        }

        simulator_config = GeoJSONFlightsSimulatorConfiguration(geojson=flight_path_geojson)
        simulator = GeoJSONFlightsSimulator(simulator_config)
        simulator.generate_flight_grid_and_path_points(altitude_of_ground_level_wgs_84=570)
        telemetry_states = simulator.generate_states(duration=30)

        return flight_declaration, telemetry_states

    def _resolve_ref(self, ref: str, context: Dict[str, Any]) -> Any:
        # ref format: "step_id.field.subfield" or just "step_id"
        parts = ref.split(".")
        step_id = parts[0]

        if "step_results" not in context:
            raise ValueError("No step results available for reference resolution")

        if step_id not in context["step_results"]:
            raise ValueError(f"Referenced step '{step_id}' not found in results")

        current_value = context["step_results"][step_id]

        # Traverse the rest of the path
        for part in parts[1:]:
            if not part:
                continue
            if isinstance(current_value, dict):
                current_value = current_value.get(part)
            elif hasattr(current_value, part):
                current_value = getattr(current_value, part)
            else:
                # If we can't find it, maybe the user meant to access a property of the result object
                # but the result object was serialized to a dict.
                raise ValueError(
                    f"Could not resolve '{part}' in '{ref}'."
                    f"Available keys: {list(current_value.keys()) if isinstance(current_value, dict) else 'Not a dict'}"
                )

        return current_value

    def _prepare_params(self, step: StepDefinition, context: Dict[str, Any], method: Any) -> Dict[str, Any]:
        params = step.parameters.copy()

        # Resolve references
        for key, value in params.items():
            if isinstance(value, dict) and "$ref" in value:
                try:
                    params[key] = self._resolve_ref(value["$ref"], context)
                    logger.info(f"Resolved reference {value['$ref']} to {params[key]}")
                except Exception as e:
                    logger.error(f"Failed to resolve reference {value['$ref']}: {e}")
                    raise

        # Inject operation_id if missing and available, AND if the method accepts it
        if "operation_id" not in params and context["operation_id"]:
            sig = inspect.signature(method)
            if "operation_id" in sig.parameters:
                params["operation_id"] = context["operation_id"]

        # Special handling for upload_flight_declaration
        if step.functionName == "upload_flight_declaration":
            if "declaration" not in params and "filename" not in params:
                params["declaration"] = context["flight_declaration"]

        # Special handling for submit_telemetry
        if step.functionName == "submit_telemetry" and "states" not in params:
            params["states"] = context["telemetry_states"]

        # # Special handling for submit_simulated_air_traffic
        # if step.functionName == "submit_simulated_air_traffic" and "observations" not in params:
        #     if "air_traffic_observations" in context:
        #         params["observations"] = context["air_traffic_observations"]

        # # Special handling for submit_air_traffic
        # if step.functionName == "submit_air_traffic" and "observations" not in params:
        #     if "air_traffic_observations" in context:
        #         params["observations"] = context["air_traffic_observations"]

        # Special handling for update_operation_state
        if step.functionName == "update_operation_state" and "new_state" in params:
            if isinstance(params["new_state"], int):
                try:
                    params["new_state"] = OperationState(params["new_state"])
                except ValueError:
                    pass

        return params

    def _execute_step(self, step: StepDefinition, resolver: DependencyResolver, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Executing step: {step.className}.{step.functionName}")

        if step.className not in self.client_map:
            raise ValueError(f"Unknown client class: {step.className}")

        client_type = self.client_map[step.className]
        client = resolver.resolve(client_type)

        method = getattr(client, step.functionName)
        params = self._prepare_params(step, context, method)

        result = method(**params)

        # Capture air traffic observations
        if step.functionName in ["generate_simulated_air_traffic_data", "fetch_data"]:
            observations = None
            if hasattr(result, "details"):
                observations = result.details
            else:
                observations = result

            context["air_traffic_observations"] = observations
            if observations is not None:
                try:
                    logger.info(f"Captured {len(observations)} air traffic observations")
                except TypeError:
                    logger.warning(f"Captured observations of type {type(observations)} which has no len()")
            else:
                logger.warning("Captured None observations")

        # Capture operation_id from result if available
        if isinstance(result, dict) and "id" in result:
            # Only update if it looks like an operation ID (UUID-ish) or if we just uploaded a declaration
            if step.functionName == "upload_flight_declaration":
                context["operation_id"] = result["id"]
                logger.info(f"Captured operation_id: {context['operation_id']}")
        elif hasattr(result, "details") and isinstance(result.details, dict):
            # Handle StepResult
            op_id = result.details.get("id")
            if op_id and step.functionName == "upload_flight_declaration":
                context["operation_id"] = op_id
                logger.info(f"Captured operation_id: {context['operation_id']}")

        # Serialize result if it's an object
        if hasattr(result, "to_dict"):
            # Use getattr to avoid type checking errors on dynamic objects
            result_data = getattr(result, "to_dict")()
        elif hasattr(result, "model_dump"):
            result_data = getattr(result, "model_dump")()
        else:
            result_data = str(result)  # Fallback

        # Store result for linking
        if step.id:
            if "step_results" not in context:
                context["step_results"] = {}
            # Store the raw result object to allow attribute access during resolution
            context["step_results"][step.id] = result

        # Determine overall status based on result content
        status_str = "success"
        if hasattr(result, "status"):
            if result.status == Status.FAIL:
                status_str = "failure"
            elif result.status == Status.PASS:
                status_str = "success"

        return {"id": step.id, "step": f"{step.className}.{step.functionName}", "status": status_str, "result": result_data}

    def _run_implicit_setup(self, resolver: DependencyResolver, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Implicit Setup: Uploading Flight Declaration")
        fb_client = cast(FlightBlenderClient, resolver.resolve(FlightBlenderClient))
        upload_result = fb_client.upload_flight_declaration(declaration=context["flight_declaration"])

        # Handle StepResult
        if hasattr(upload_result, "details") and isinstance(upload_result.details, dict):
            op_id = upload_result.details.get("id")
            if op_id:
                context["operation_id"] = op_id
                logger.info(f"Setup complete. Operation ID: {op_id}")

                result_data = getattr(upload_result, "model_dump")() if hasattr(upload_result, "model_dump") else str(upload_result)
                return {"step": "Setup: Upload Flight Declaration", "status": "success", "result": result_data}
            else:
                raise ValueError("Failed to get operation ID from upload result")
        else:
            # Check if it failed
            if hasattr(upload_result, "status") and upload_result.status == Status.FAIL:
                raise ValueError(f"Setup failed: {upload_result.error_message}")
            raise ValueError(f"Unexpected return from upload: {upload_result}")

    def _run_implicit_teardown(self, resolver: DependencyResolver, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Implicit Teardown: Deleting Operation {context['operation_id']}")
        fb_client = cast(FlightBlenderClient, resolver.resolve(FlightBlenderClient))
        teardown_result = fb_client.delete_flight_declaration(context["operation_id"])

        result_data = getattr(teardown_result, "model_dump")() if hasattr(teardown_result, "model_dump") else str(teardown_result)
        return {"step": "Teardown: Delete Flight Declaration", "status": "success", "result": result_data}

    def run_scenario(self, scenario: ScenarioDefinition) -> List[Dict[str, Any]]:
        results = []

        # Pre-generate data
        try:
            flight_declaration, telemetry_states = self._generate_data()
        except Exception as e:
            logger.error(f"Data generation failed: {e}")
            return [{"step": "Data Generation", "status": "error", "error": str(e)}]

        context = {"operation_id": None, "flight_declaration": flight_declaration, "telemetry_states": telemetry_states, "step_results": {}}

        # Check if user provided setup
        user_has_setup = len(scenario.steps) > 0 and scenario.steps[0].functionName == "upload_flight_declaration"

        with ExitStack() as stack:
            resolver = DependencyResolver(stack)

            try:
                # Implicit Setup
                if not user_has_setup:
                    try:
                        setup_result = self._run_implicit_setup(resolver, context)
                        results.append(setup_result)
                    except Exception as setup_error:
                        logger.error(f"Implicit setup failed: {setup_error}")
                        return [{"step": "Implicit Setup", "status": "error", "error": str(setup_error)}]

                for step in scenario.steps:
                    try:
                        step_result = self._execute_step(step, resolver, context)
                        results.append(step_result)
                    except Exception as e:
                        logger.error(f"Error in step {step.functionName}: {e}")
                        results.append({"step": f"{step.className}.{step.functionName}", "status": "error", "error": str(e)})
                        # Stop on error?
                        break
            except Exception as e:
                logger.error(f"Scenario execution failed: {e}")
                results.append({"step": "Scenario Setup", "status": "error", "error": str(e)})
            finally:
                # Implicit Teardown
                if not user_has_setup and context["operation_id"]:
                    try:
                        teardown_result = self._run_implicit_teardown(resolver, context)
                        results.append(teardown_result)
                    except Exception as teardown_error:
                        logger.error(f"Teardown failed: {teardown_error}")
                        results.append({"step": "Teardown", "status": "error", "error": str(teardown_error)})

        return results
