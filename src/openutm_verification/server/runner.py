import asyncio
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Type, TypeVar, cast

import yaml
from loguru import logger
from pydantic import BaseModel

from openutm_verification.core.execution.config_models import AppConfig, ConfigProxy, DataFiles
from openutm_verification.core.execution.definitions import ScenarioDefinition, StepDefinition
from openutm_verification.core.execution.dependency_resolution import CONTEXT, DEPENDENCIES, DependencyResolver, call_with_dependencies
from openutm_verification.core.execution.scenario_runner import STEP_REGISTRY, ScenarioContext, _scenario_state, scenario_step
from openutm_verification.core.reporting.reporting_models import Status, StepResult
from openutm_verification.scenarios.common import generate_flight_declaration, generate_telemetry
from openutm_verification.server.introspection import process_method

T = TypeVar("T")


class SessionManager:
    _instance = None
    _initialized: bool

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: str = "config/default.yaml"):
        if hasattr(self, "_initialized") and self._initialized:
            return

        config_path = os.environ.get("OPENUTM_CONFIG_PATH", config_path)

        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.client_map: Dict[str, Type] = {}
        for dep_type in DEPENDENCIES:
            if isinstance(dep_type, type) and dep_type.__name__.endswith("Client"):
                self.client_map[dep_type.__name__] = dep_type

        self.session_stack: AsyncExitStack | None = None
        self.session_resolver: DependencyResolver | None = None
        self.session_context: ScenarioContext | None = None
        self.session_tasks: Dict[str, asyncio.Task] = {}
        self._initialized = True

    @scenario_step("Join Background Task")
    async def join_task(self, task_id: str) -> Any:
        """Wait for a background task to complete and return its result.

        Args:
            task_id: The ID of the background task to join.
        Returns:
            The result of the background task.
        """
        if task_id not in self.session_tasks:
            raise ValueError(f"Task ID '{task_id}' not found in session tasks")

        task = self.session_tasks[task_id]
        result = await task
        return result

    async def initialize_session(self):
        logger.info("Initializing new session")
        if self.session_stack:
            await self.close_session()

        self.session_stack = AsyncExitStack()
        self.session_resolver = DependencyResolver(self.session_stack)

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

            self.session_context = ScenarioContext()
            with self.session_context:
                if flight_declaration:
                    ScenarioContext.set_flight_declaration_data(flight_declaration)
                if telemetry_states:
                    ScenarioContext.set_telemetry_data(telemetry_states)

        except Exception as e:
            logger.error(f"Data generation failed: {e}")

    async def close_session(self):
        logger.info("Closing session")
        if self.session_stack:
            await self.session_stack.aclose()
            self.session_stack = None
            self.session_resolver = None
            self.session_context = None
            _scenario_state.set(None)

    def _resolve_ref(self, ref: str) -> Any:
        # ref format: "step_id.field.subfield" or just "step_id"
        parts = ref.split(".")
        step_id = parts[0]

        if not self.session_context or not self.session_context.state:
            raise ValueError("No active scenario context or state available")

        state = self.session_context.state

        if step_id not in state.step_results:
            raise ValueError(f"Referenced step '{step_id}' not found in results")

        current_value = state.step_results[step_id]

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

    def resolve_references_in_params(self, params: Dict[str, Any]) -> None:
        for key, value in params.items():
            if isinstance(value, dict) and "$ref" in value:
                try:
                    params[key] = self._resolve_ref(value["$ref"])
                    logger.info(f"Resolved reference {value['$ref']} to {params[key]}")
                except Exception as e:
                    logger.error(f"Failed to resolve reference {value['$ref']}: {e}")
                    raise

    def get_available_operations(self) -> List[Dict[str, Any]]:
        operations = []
        for entry in STEP_REGISTRY.values():
            method = getattr(entry.client_class, entry.method_name)
            op_info = process_method(entry.client_class, method)
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

    def validate_params(self, params: Dict[str, Any], step_name: str) -> None:
        if step_name not in STEP_REGISTRY:
            raise ValueError(f"Step '{step_name}' not found in registry")

        entry = STEP_REGISTRY[step_name]
        DynamicModel = entry.param_model

        # Create a dynamic Pydantic model for validation
        try:
            validated_data = DynamicModel(**params)
            # Update params with validated data (coerced types, defaults)
            params.update(validated_data.model_dump())
        except Exception as e:
            logger.error(f"Validation error for step '{step_name}': {e}")
            raise ValueError(f"Invalid parameters for step '{step_name}': {e}")

    def _prepare_params(self, step: StepDefinition) -> Dict[str, Any]:
        params = step.parameters.copy()

        # Resolve references
        self.resolve_references_in_params(params)
        self.validate_params(params, step.name)

        return params

    def _serialize_result(self, result: Any) -> Any:
        if isinstance(result, BaseModel):
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

    async def _execute_step(self, step: StepDefinition) -> Dict[str, Any]:
        assert self.session_resolver is not None and self.session_context is not None
        if step.name not in STEP_REGISTRY:
            raise ValueError(f"Step '{step.name}' not found in registry")

        entry = STEP_REGISTRY[step.name]
        client = await self.session_resolver.resolve(entry.client_class)

        method = getattr(client, entry.method_name)

        # Prepare parameters (resolve refs, inject context)
        kwargs = self._prepare_params(step)

        if step.run_in_background:
            logger.info(f"Executing step '{step.name}' in background")
            task = asyncio.create_task(call_with_dependencies(method, resolver=self.session_resolver, **kwargs))
            self.session_tasks[step.id] = task
            self.session_context.add_result(StepResult(id=step.id, name=step.name, status=Status.RUNNING, details={"task_id": step.id}, duration=0.0))
            return {"id": step.id, "step": step.name, "status": "running", "task_id": step.id}
        # Execute with dependencies
        result = await call_with_dependencies(method, resolver=self.session_resolver, **kwargs)

        # If result is a StepResult and we have a step ID, update the ID in the result object
        # This updates the object in state.steps as well since it's the same reference
        if step.id and hasattr(result, "id"):
            result.id = step.id

        # Serialize result if it's an object
        result_data = self._serialize_result(result)

        # Determine overall status based on result content
        status_str = self._determine_status(result)

        return {"id": step.id, "step": step.name, "status": status_str, "result": result_data}

    async def execute_single_step(self, step: StepDefinition) -> Dict[str, Any]:
        if not self.session_resolver:
            logger.info("Session resolver not found, initializing session")
            await self.initialize_session()

        assert self.session_resolver is not None

        # Set scenario state context for this execution
        if not self.session_context:
            raise ValueError("Session context not initialized")

        try:
            with self.session_context:
                # Ensure state is available after entering context
                if not self.session_context.state:
                    raise ValueError("Scenario state not initialized")
                return await self._execute_step(step)
        except Exception as e:
            logger.error(f"Error executing step {step.name}: {e}")
            raise
            return {"step": step.name, "status": "error", "error": str(e)}

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

    async def execute_function(self, func: Callable[..., Coroutine[Any, Any, T]]) -> T:
        if not self.session_resolver:
            await self.initialize_session()

        assert self.session_resolver is not None

        if not self.session_context:
            raise ValueError("Session context not initialized")

        with self.session_context:
            return await call_with_dependencies(func, resolver=self.session_resolver)
