import inspect
import json
import re
from contextlib import AsyncExitStack
from enum import Enum
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
from openutm_verification.core.clients.system.system_client import SystemClient
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
    run_in_background: bool = False


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
            "SystemClient": SystemClient,
        }
        self.session_stack: AsyncExitStack | None = None
        self.session_resolver: DependencyResolver | None = None
        self.session_context: Dict[str, Any] = {}

    async def initialize_session(self):
        if self.session_stack:
            await self.close_session()

        self.session_stack = AsyncExitStack()
        self.session_resolver = DependencyResolver(self.session_stack)

        # Pre-generate data
        try:
            flight_declaration, telemetry_states = self._generate_data()
            self.session_context = {
                "operation_id": None,
                "flight_declaration": flight_declaration,
                "telemetry_states": telemetry_states,
                "step_results": {},
            }
        except Exception as e:
            logger.error(f"Data generation failed: {e}")
            raise

    async def close_session(self):
        if self.session_stack:
            await self.session_stack.aclose()
            self.session_stack = None
            self.session_resolver = None
            self.session_context = {}

    async def execute_single_step(self, step: StepDefinition) -> Dict[str, Any]:
        if not self.session_resolver:
            await self.initialize_session()

        try:
            return await self._execute_step(step, self.session_resolver, self.session_context)
        except Exception as e:
            logger.error(f"Error executing step {step.functionName}: {e}")
            return {"step": f"{step.className}.{step.functionName}", "status": "error", "error": str(e)}

    def _process_parameter(self, param_name: str, param: inspect.Parameter) -> Dict[str, Any] | None:
        if param_name == "self":
            return None

        annotation = param.annotation
        default = param.default

        # Handle Type
        type_str = "Any"
        is_enum = False
        options = None

        if annotation != inspect.Parameter.empty:
            # Check for Enum
            if inspect.isclass(annotation) and issubclass(annotation, Enum):
                is_enum = True
                type_str = annotation.__name__
                options = [{"name": e.name, "value": e.value} for e in annotation]
            else:
                # Clean up type string
                type_str = str(annotation)
                # Use regex to remove module paths (e.g. "list[openutm_verification.models.FlightObservation]" -> "list[FlightObservation]")
                type_str = re.sub(r"([a-zA-Z_][a-zA-Z0-9_]*\.)+", "", type_str)
                # Remove <class '...'> wrapper if present
                if type_str.startswith("<class '") and type_str.endswith("'>"):
                    type_str = type_str[8:-2]

        # Handle Default
        default_val = None
        if default != inspect.Parameter.empty:
            if default is None:
                default_val = None
            # If default is an Enum member, get its value
            elif isinstance(default, Enum):
                default_val = default.value
            else:
                default_val = str(default)

        param_info = {"name": param_name, "type": type_str, "default": default_val, "required": default == inspect.Parameter.empty}

        if is_enum:
            param_info["isEnum"] = True
            param_info["options"] = options

        return param_info

    def _process_method(self, class_name: str, client_class: Type, name: str, method: Any) -> Dict[str, Any] | None:
        if not hasattr(method, "_is_scenario_step"):
            return None

        step_name = getattr(method, "_step_name")
        sig = inspect.signature(method)
        parameters = []
        for param_name, param in sig.parameters.items():
            param_info = self._process_parameter(param_name, param)
            if param_info:
                parameters.append(param_info)

        return {
            "id": f"{class_name}.{name}",
            "name": step_name,
            "functionName": name,
            "className": class_name,
            "description": inspect.getdoc(method) or "",
            "parameters": parameters,
            "filePath": inspect.getfile(client_class),
        }

    def get_available_operations(self) -> List[Dict[str, Any]]:
        operations = []
        for class_name, client_class in self.client_map.items():
            for name, method in inspect.getmembers(client_class):
                op_info = self._process_method(class_name, client_class, name, method)
                if op_info:
                    operations.append(op_info)
        return operations

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

        # Handle parameter renaming for initialize_verify_sdsp_track
        if step.functionName == "initialize_verify_sdsp_track":
            if "expected_heartbeat_interval_seconds" in params:
                params["expected_track_interval_seconds"] = params.pop("expected_heartbeat_interval_seconds")
            if "expected_heartbeat_count" in params:
                params["expected_track_count"] = params.pop("expected_heartbeat_count")

        # Handle parameter renaming for setup_flight_declaration
        if step.functionName == "setup_flight_declaration":
            if "telemetry_path" in params:
                params["trajectory_path"] = params.pop("telemetry_path")

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

    async def _execute_step(self, step: StepDefinition, resolver: DependencyResolver, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Executing step: {step.className}.{step.functionName}")

        if step.className not in self.client_map:
            raise ValueError(f"Unknown client class: {step.className}")

        # Special handling for SystemClient.join_task
        if step.className == "SystemClient" and step.functionName == "join_task":
            task_id_param = step.parameters.get("task_id")
            if not task_id_param:
                raise ValueError("task_id is required for join_task")

            # Handle if task_id is passed as a dictionary (from a previous step result)
            if isinstance(task_id_param, dict) and "task_id" in task_id_param:
                task_id = task_id_param["task_id"]
            else:
                task_id = str(task_id_param)

            background_tasks = context.get("background_tasks", {})
            if task_id not in background_tasks:
                raise ValueError(f"Background task {task_id} not found")

            logger.info(f"Joining background task {task_id}")
            task = background_tasks[task_id]
            result = await task
            # Clean up
            del background_tasks[task_id]

            # Continue to result processing...
        else:
            client_type = self.client_map[step.className]
            client = await resolver.resolve(client_type)

            method = getattr(client, step.functionName)
            params = self._prepare_params(step, context, method)

            if step.run_in_background:
                import asyncio
                import uuid

                task_id = str(uuid.uuid4())
                logger.info(f"Starting background task {task_id} for {step.className}.{step.functionName}")

                # Create a coroutine but don't await it yet
                coro = method(**params)
                if not inspect.isawaitable(coro):
                    # If it's not async, wrap it? For now assume async.
                    pass

                task = asyncio.create_task(coro)
                context.setdefault("background_tasks", {})[task_id] = task

                result = {"task_id": task_id, "status": "running"}

                # Store result for referencing
                if step.id:
                    context.setdefault("step_results", {})[step.id] = result

                return {"id": step.id, "step": f"{step.className}.{step.functionName}", "status": "running", "result": result}

            result = method(**params)
            if inspect.isawaitable(result):
                result = await result

            # Store result for referencing
            if step.id:
                context.setdefault("step_results", {})[step.id] = result
                logger.info(f"Stored result for step {step.id}")
            else:
                logger.warning(f"No step ID provided, result not stored for {step.functionName}")

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

    async def _run_implicit_teardown(self, resolver: DependencyResolver, context: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"Implicit Teardown: Deleting Operation {context['operation_id']}")
        fb_client = cast(FlightBlenderClient, await resolver.resolve(FlightBlenderClient))
        # delete_flight_declaration uses the stored latest_flight_declaration_id in the client instance
        teardown_result = await fb_client.delete_flight_declaration()

        result_data = getattr(teardown_result, "model_dump")() if hasattr(teardown_result, "model_dump") else str(teardown_result)
        return {"step": "Teardown: Delete Flight Declaration", "status": "success", "result": result_data}

    async def run_scenario(self, scenario: ScenarioDefinition) -> List[Dict[str, Any]]:
        results = []

        # Pre-generate data
        try:
            flight_declaration, telemetry_states = self._generate_data()
        except Exception as e:
            logger.error(f"Data generation failed: {e}")
            return [{"step": "Data Generation", "status": "error", "error": str(e)}]

        context = {"operation_id": None, "flight_declaration": flight_declaration, "telemetry_states": telemetry_states, "step_results": {}}

        async with AsyncExitStack() as stack:
            resolver = DependencyResolver(stack)

            try:
                for step in scenario.steps:
                    try:
                        step_result = await self._execute_step(step, resolver, context)
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
                if context["operation_id"]:
                    try:
                        teardown_result = await self._run_implicit_teardown(resolver, context)
                        results.append(teardown_result)
                    except Exception as teardown_error:
                        logger.error(f"Teardown failed: {teardown_error}")
                        results.append({"step": "Teardown", "status": "error", "error": str(teardown_error)})

        return results
