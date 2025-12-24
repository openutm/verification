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
from openutm_verification.core.execution.config_models import AppConfig, ConfigProxy, DataFiles
from openutm_verification.core.execution.dependency_resolution import CONTEXT, DEPENDENCIES, DependencyResolver
from openutm_verification.core.execution.scenario_runner import ScenarioState, _scenario_state
from openutm_verification.core.reporting.reporting_models import Status, StepResult
from openutm_verification.models import OperationState
from openutm_verification.scenarios.common import generate_flight_declaration, generate_telemetry
from openutm_verification.server.introspection import process_method


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
        self.client_map: Dict[str, Type] = {}
        for dep_type in DEPENDENCIES:
            if isinstance(dep_type, type) and dep_type.__name__.endswith("Client"):
                self.client_map[dep_type.__name__] = dep_type

        self.session_stack: AsyncExitStack | None = None
        self.session_resolver: DependencyResolver | None = None
        self.session_context: Dict[str, Any] = {}

    async def initialize_session(self):
        logger.info("Initializing new session")
        if self.session_stack:
            await self.close_session()

        self.session_stack = AsyncExitStack()
        self.session_resolver = DependencyResolver(self.session_stack)

        # Set up context for dependencies
        # We use a default context so dependencies like DataFiles can be resolved
        suite_name = next(iter(self.config.suites.keys()), "default")

        CONTEXT.set(
            {
                "scenario_id": "interactive_session",
                "suite_scenario": None,
                "suite_name": suite_name,
                "docs": None,
            }
        )

        # Pre-generate data using resolved DataFiles
        try:
            data_files = cast(DataFiles, await self.session_resolver.resolve(DataFiles))
            flight_declaration, telemetry_states = self._generate_data(data_files)

            scenario_state = ScenarioState(active=True, flight_declaration_data=flight_declaration, telemetry_data=telemetry_states)

            self.session_context = {
                "operation_id": None,
                "flight_declaration": flight_declaration,
                "telemetry_states": telemetry_states,
                "step_results": {},
                "scenario_state": scenario_state,
            }
        except Exception as e:
            logger.error(f"Data generation failed: {e}")

    async def close_session(self):
        logger.info("Closing session")
        if self.session_stack:
            await self.session_stack.aclose()
            self.session_stack = None
            self.session_resolver = None
            self.session_context = {}

    async def execute_single_step(self, step: StepDefinition) -> Dict[str, Any]:
        if not self.session_resolver:
            logger.info("Session resolver not found, initializing session")
            await self.initialize_session()

        assert self.session_resolver is not None

        # Set scenario state context for this execution
        token = None
        if "scenario_state" in self.session_context:
            token = _scenario_state.set(self.session_context["scenario_state"])

        try:
            return await self._execute_step(step, self.session_resolver, self.session_context)
        except Exception as e:
            logger.error(f"Error executing step {step.functionName}: {e}")
            return {"step": f"{step.className}.{step.functionName}", "status": "error", "error": str(e)}
        finally:
            if token:
                _scenario_state.reset(token)

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
                raise ValueError(
                    f"Could not resolve '{part}' in '{ref}'."
                    f"Available keys: {list(current_value.keys()) if isinstance(current_value, dict) else 'Not a dict'}"
                )

        return current_value

    def _resolve_references_in_params(self, params: Dict[str, Any], context: Dict[str, Any]) -> None:
        for key, value in params.items():
            if isinstance(value, dict) and "$ref" in value:
                try:
                    params[key] = self._resolve_ref(value["$ref"], context)
                    logger.info(f"Resolved reference {value['$ref']} to {params[key]}")
                except Exception as e:
                    logger.error(f"Failed to resolve reference {value['$ref']}: {e}")
                    raise

    def _prepare_params(self, step: StepDefinition, context: Dict[str, Any]) -> Dict[str, Any]:
        params = step.parameters.copy()

        # Resolve references
        self._resolve_references_in_params(params, context)

        # Special handling for submit_telemetry
        if step.functionName == "submit_telemetry" and "states" not in params:
            params["states"] = context["telemetry_states"]

        # Special handling for update_operation_state
        if step.functionName == "update_operation_state" and "new_state" in params:
            if isinstance(params["new_state"], int):
                try:
                    params["new_state"] = OperationState(params["new_state"])
                except ValueError:
                    pass

        return params

    def _serialize_result(self, result: Any) -> Any:
        if hasattr(result, "to_dict"):
            return getattr(result, "to_dict")()
        elif isinstance(result, BaseModel):
            return result.model_dump()
        else:
            return result

    def _determine_status(self, result: Any) -> str:
        if hasattr(result, "status"):
            status_val = getattr(result, "status")
            if status_val == Status.FAIL:
                return "failure"
            elif status_val == Status.PASS:
                return "success"
        return "success"

    async def _execute_step(self, step: StepDefinition, resolver: DependencyResolver, context: Dict[str, Any]) -> Dict[str, Any]:
        client_class = self.client_map[step.className]
        client = await resolver.resolve(client_class)

        method = getattr(client, step.functionName)

        # Prepare parameters (resolve refs, inject context)
        kwargs = self._prepare_params(step, context)

        # Inject dependencies if missing
        sig = inspect.signature(method)
        for name, param in sig.parameters.items():
            if name == "self" or name in kwargs:
                continue

            if param.annotation in DEPENDENCIES:
                kwargs[name] = await resolver.resolve(param.annotation)

        result = await method(**kwargs)

        # Serialize result if it's an object
        result_data = self._serialize_result(result)

        # Store result for linking
        if step.id:
            if "step_results" not in context:
                context["step_results"] = {}
            context["step_results"][step.id] = result

        # Determine overall status based on result content
        status_str = self._determine_status(result)

        # Add to scenario state if not already added by decorator
        # The decorator adds it, but if the method wasn't decorated, we might want to add it here?
        # Most client methods are decorated. If we add it again, we might duplicate.
        # Let's assume the decorator handles it if present.

        return {"id": step.id, "step": f"{step.className}.{step.functionName}", "status": status_str, "result": result_data}

    def get_available_operations(self) -> List[Dict[str, Any]]:
        operations = []
        for class_name, client_class in self.client_map.items():
            for name, method in inspect.getmembers(client_class):
                op_info = process_method(class_name, client_class, name, method)
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

    def _generate_data(self, data_files: DataFiles):
        flight_declaration = None
        telemetry_states = None

        if data_files.flight_declaration:
            try:
                flight_declaration = generate_flight_declaration(data_files.flight_declaration)
            except Exception as e:
                logger.warning(f"Could not generate flight declaration: {e}")

        if data_files.trajectory:
            try:
                telemetry_states = generate_telemetry(data_files.trajectory)
            except Exception as e:
                logger.warning(f"Could not generate telemetry: {e}")

        return flight_declaration, telemetry_states

    async def run_scenario(self, scenario: ScenarioDefinition) -> List[Dict[str, Any]]:
        results = []
        if not self.session_resolver:
            await self.initialize_session()

        for step in scenario.steps:
            result = await self.execute_single_step(step)
            results.append(result)
            if result.get("status") == "error":
                break
        return results
