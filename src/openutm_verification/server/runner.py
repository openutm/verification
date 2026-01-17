import asyncio
import os
import re
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Type, TypeVar, cast

import yaml
from loguru import logger
from pydantic import BaseModel

from openutm_verification.core.execution.conditions import ConditionEvaluator
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
        self.data_files: DataFiles | None = None
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
            self.data_files = cast(DataFiles, await self.session_resolver.resolve(DataFiles))
            flight_declaration, telemetry_states = self._generate_data(self.data_files)

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
        if ref.startswith("data_files."):
            if not self.data_files:
                raise ValueError("Data files not initialized")
            parts = ref.split(".")
            if len(parts) != 2:
                raise ValueError(f"Invalid data_files reference: {ref}")
            attr = parts[1]
            if not hasattr(self.data_files, attr):
                raise ValueError(f"Data file '{attr}' not found")
            return getattr(self.data_files, attr)

        if not ref.startswith("steps."):
            # Fallback for legacy refs if any, or just error
            raise ValueError(f"Invalid reference format: {ref}. Expected 'steps.<step_name>.result...' or 'data_files.<name>'")

        parts = ref.split(".")
        if len(parts) < 3:
            raise ValueError(f"Invalid reference format: {ref}. Expected 'steps.<step_name>.result...'")

        step_name = parts[1]
        # parts[2] is likely "result" or "details"

        if not self.session_context or not self.session_context.state:
            raise ValueError("No active scenario context or state available")

        state = self.session_context.state

        if step_name not in state.step_results:
            logger.error(f"Step '{step_name}' not found in results. Available steps: {list(state.step_results.keys())}")
            raise ValueError(f"Referenced step '{step_name}' not found in results")

        step_result = state.step_results[step_name]

        # Start traversing from the step result object
        current_value = step_result

        # Skip "steps" and "step_name"
        remaining_parts = parts[2:]

        # Handle "result" alias for "details"
        if remaining_parts[0] == "result":
            remaining_parts[0] = "details"

        for part in remaining_parts:
            if not part:
                continue
            if isinstance(current_value, dict):
                current_value = current_value.get(part)
            elif hasattr(current_value, part):
                current_value = getattr(current_value, part)
            else:
                raise ValueError(
                    f"Could not resolve '{part}' in '{ref}'."
                    f"Available keys: {list(current_value.keys()) if isinstance(current_value, dict) else dir(current_value)}"
                )

        return current_value

    def resolve_references_in_params(self, params: Dict[str, Any]) -> None:
        # Regex to find ${{ ... }} patterns
        pattern = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")

        def resolve_value(value: Any) -> Any:
            if isinstance(value, str):
                match = pattern.fullmatch(value)
                if match:
                    # Entire string is a reference
                    ref = match.group(1)
                    try:
                        resolved = self._resolve_ref(ref)
                        logger.info(f"Resolved reference {ref} to {resolved}")
                        return resolved
                    except Exception as e:
                        logger.error(f"Failed to resolve reference {ref}: {e}")
                        raise

                # Check for partial matches (string interpolation)
                # For now, let's only support full matches for simplicity and type safety
                # If we need interpolation "Session ID: ${{ ... }}", we can add it later.
                return value
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(v) for v in value]
            return value

        for key, value in params.items():
            params[key] = resolve_value(value)

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
            ConfigProxy._config = None
            ConfigProxy.initialize(config)

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

    def _prepare_params(self, step: StepDefinition) -> Dict[str, Any]:
        params = step.arguments.copy() if step.arguments else {}
        self.resolve_references_in_params(params)
        return params

    def _serialize_result(self, result: Any) -> Any:
        if isinstance(result, BaseModel):
            return result.model_dump()
        return result

    def _determine_status(self, result: Any) -> str:
        if isinstance(result, StepResult):
            if result.status == Status.FAIL:
                return "failure"
            elif result.status == Status.PASS:
                return "success"
        return "success"

    async def _execute_step(self, step: StepDefinition) -> Dict[str, Any]:
        assert self.session_resolver is not None and self.session_context is not None
        if step.step not in STEP_REGISTRY:
            raise ValueError(f"Step '{step.step}' not found in registry")

        entry = STEP_REGISTRY[step.step]
        client = await self.session_resolver.resolve(entry.client_class)

        method = getattr(client, entry.method_name)

        # Prepare parameters (resolve refs, inject context)
        kwargs = self._prepare_params(step)

        if step.background:
            step_id = step.id or step.step
            logger.info(f"Executing step '{step_id}' ({step.step}) in background")
            task = asyncio.create_task(call_with_dependencies(method, resolver=self.session_resolver, **kwargs))
            self.session_tasks[step_id] = task
            self.session_context.add_result(StepResult(id=step_id, name=step.step, status=Status.RUNNING, details={"task_id": step_id}, duration=0.0))
            return {"id": step_id, "step": step.step, "status": "running", "task_id": step_id}

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

        # Add result to context
        step_id = step.id or step.step
        logger.info(f"Adding result for step '{step_id}' (name: {step.step}) to context")

        # If the result is already a StepResult (from scenario_step decorator), use it directly but ensure ID is correct
        if isinstance(result, StepResult):
            result.id = step_id
            # We don't need to add it again if it was already added by the decorator,
            # but the decorator adds it with a generated ID or no ID if not running in full scenario context?
            # Actually, the decorator adds it to ScenarioContext.add_result(step_result).
            # Let's check if we need to update it or add it.

            # The decorator adds the result to the context.
            # If we add it again here, we might duplicate it or overwrite it.
            # However, the decorator doesn't know the 'step.id' from the YAML, it only knows the function execution.
            # So we should probably update the existing result in the context if possible, or ensure the ID matches.

            # Let's just ensure the result in the context has the correct ID.
            # The decorator calls ScenarioContext.add_result(step_result).
            # step_result.id might be None or something else.

            # Since we are in the runner, we want to ensure the result is stored with the step_id we expect.
            # We can remove the old one (if any) and add the updated one.
            self.session_context.add_result(result)
        else:
            self.session_context.add_result(StepResult(id=step_id, name=step.step, status=Status.PASS, details=result_data, duration=0.0))

        return {"id": step.id, "step": step.step, "status": status_str, "result": result_data}

    async def execute_single_step(self, step: StepDefinition) -> Dict[str, Any]:
        if not self.session_resolver or not self.session_context:
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
            step_id = step.id or step.step
            logger.error(f"Error executing step {step_id}: {e}")
            raise

    async def run_scenario(self, scenario: ScenarioDefinition) -> List[Dict[str, Any]]:
        results = []
        if not self.session_resolver:
            await self.initialize_session()

        # Validate and prepare steps
        seen_ids = set()
        for step in scenario.steps:
            if not step.id:
                step.id = step.step

            if step.id in seen_ids:
                raise ValueError(f"Duplicate step ID found: '{step.id}'. Step IDs must be unique within a scenario.")
            seen_ids.add(step.id)

        for step in scenario.steps:
            # Evaluate condition if present
            if step.if_condition:
                step_results_dict = {}
                if self.session_context and self.session_context.state:
                    step_results_dict = self.session_context.state.step_results

                evaluator = ConditionEvaluator(step_results_dict)
                should_run = evaluator.evaluate(step.if_condition)

                if not should_run:
                    logger.info(f"Skipping step '{step.id}' due to condition: {step.if_condition}")
                    # Record as skipped
                    skipped_result = StepResult(
                        id=step.id or step.step,
                        name=step.step,
                        status=Status.SKIP,
                        duration=0.0,
                        result=None,
                        message=f"Skipped due to condition: {step.if_condition}",
                    )
                    ScenarioContext.add_result(skipped_result)
                    results.append({"id": step.id, "status": "skipped", "result": None, "message": f"Condition not met: {step.if_condition}"})
                    continue

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


# Import dependencies to ensure they are registered
import openutm_verification.core.execution.dependencies  # noqa: E402, F401
