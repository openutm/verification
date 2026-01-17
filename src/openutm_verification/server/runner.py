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
from openutm_verification.core.execution.scenario_runner import STEP_REGISTRY, ScenarioContext, _scenario_state
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

    def _resolve_ref(self, ref: str, loop_context: Dict[str, Any] | None = None) -> Any:
        # Handle loop variables first
        if ref.startswith("loop."):
            if not loop_context:
                raise ValueError(f"Loop variable '{ref}' used outside of loop context")
            parts = ref.split(".")
            if len(parts) != 2:
                raise ValueError(f"Loop reference must be 'loop.index' or 'loop.item', got '{ref}'")
            field = parts[1]
            if field == "index":
                return loop_context.get("index", 0)
            elif field == "item":
                if "item" not in loop_context:
                    raise ValueError("loop.item used but no item in loop context")
                return loop_context["item"]
            else:
                raise ValueError(f"Unknown loop field '{field}', must be 'index' or 'item'")

        # Handle group.step_id.result references
        if ref.startswith("group."):
            if not loop_context or "group_context" not in loop_context:
                raise ValueError(f"Group variable '{ref}' used outside of group context")
            parts = ref.split(".")
            if len(parts) < 3:
                raise ValueError(f"Group reference must be 'group.step_id.result...', got '{ref}'")
            step_id = parts[1]
            # Remaining parts start from index 2 (e.g., 'result', 'result.field', etc.)
            group_context = loop_context["group_context"]
            if step_id not in group_context:
                raise ValueError(f"Step '{step_id}' not found in group context. Available: {list(group_context.keys())}")

            current_value = group_context[step_id]
            # Traverse remaining parts starting from parts[2]
            remaining_parts = parts[2:]
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

        # Handle legacy "details" alias, now standardized to "result"
        if remaining_parts[0] == "details":
            remaining_parts[0] = "result"

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

    def resolve_references_in_params(self, params: Dict[str, Any], loop_context: Dict[str, Any] | None = None) -> None:
        # Regex to find ${{ ... }} patterns
        pattern = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")
        loop_context = loop_context or {}

        def resolve_value(value: Any) -> Any:
            if isinstance(value, str):
                match = pattern.fullmatch(value)
                if match:
                    # Entire string is a reference
                    ref = match.group(1)
                    try:
                        resolved = self._resolve_ref(ref, loop_context)
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

    def _prepare_params(self, step: StepDefinition, loop_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        params = step.arguments.copy() if step.arguments else {}
        self.resolve_references_in_params(params, loop_context)
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

    def _record_background_result(self, step_id: str, step_name: str, task: asyncio.Task) -> None:
        """Attach a completion handler so background steps store their final result."""

        def _on_done(t: asyncio.Task) -> None:
            if not self.session_context:
                return

            try:
                res = t.result()
                if isinstance(res, StepResult):
                    res.id = step_id
                    self.session_context.add_result(res)
                    return

                result_data = self._serialize_result(res)
                status_str = self._determine_status(res)
                status = Status.PASS if status_str == "success" else Status.FAIL
                self.session_context.add_result(StepResult(id=step_id, name=step_name, status=status, result=result_data, duration=0.0))
            except Exception as exc:  # noqa: BLE001
                self.session_context.add_result(StepResult(id=step_id, name=step_name, status=Status.FAIL, error_message=str(exc), duration=0.0))

        task.add_done_callback(_on_done)

    async def _execute_step(self, step: StepDefinition, loop_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        assert self.session_resolver is not None and self.session_context is not None
        if step.step not in STEP_REGISTRY:
            raise ValueError(f"Step '{step.step}' not found in registry")

        entry = STEP_REGISTRY[step.step]
        client = await self.session_resolver.resolve(entry.client_class)

        method = getattr(client, entry.method_name)

        # Prepare parameters (resolve refs, inject context)
        kwargs = self._prepare_params(step, loop_context)

        if step.background:
            step_id = step.id or step.step
            logger.info(f"Executing step '{step_id}' ({step.step}) in background")
            task = asyncio.create_task(call_with_dependencies(method, resolver=self.session_resolver, **kwargs))
            self.session_tasks[step_id] = task
            self.session_context.add_result(StepResult(id=step_id, name=step.step, status=Status.RUNNING, result={"task_id": step_id}, duration=0.0))
            self._record_background_result(step_id, step.step, task)
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
            self.session_context.add_result(StepResult(id=step_id, name=step.step, status=Status.PASS, result=result_data, duration=0.0))

        return {"id": step.id, "step": step.step, "status": status_str, "result": result_data}

    async def execute_single_step(self, step: StepDefinition, loop_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
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
                return await self._execute_step(step, loop_context)
        except Exception as e:
            step_id = step.id or step.step
            logger.error(f"Error executing step {step_id}: {e}")
            raise

    def _is_group_reference(self, step_name: str, scenario: ScenarioDefinition) -> bool:
        """Check if a step name references a group."""
        return step_name in scenario.groups

    async def _execute_group(
        self, step: StepDefinition, scenario: ScenarioDefinition, loop_context: Dict[str, Any] | None = None
    ) -> List[Dict[str, Any]]:
        """Execute a group of steps."""
        group_name = step.step
        if group_name not in scenario.groups:
            raise ValueError(f"Group '{group_name}' not found in scenario")

        group = scenario.groups[group_name]
        results = []
        group_context = {}  # Store results within this group execution

        # Create enhanced loop context with group_context
        enhanced_loop_context = (loop_context or {}).copy()
        enhanced_loop_context["group_context"] = group_context

        logger.info(f"Executing group '{group_name}' with {len(group.steps)} steps")

        for group_step in group.steps:
            # Ensure each step has an ID
            if not group_step.id:
                group_step.id = group_step.step

            # Execute the step with the enhanced context
            result = await self.execute_single_step(group_step, enhanced_loop_context)
            results.append(result)

            # Store result in group context for subsequent steps
            # Store the entire result dict so nested access works (group.step_id.result)
            group_context[group_step.id] = result

            # If step failed and it's not allowed to fail, break the group
            if result.get("status") == "error":
                logger.error(f"Group step '{group_step.id}' failed, stopping group execution")
                break

        return results

    async def _wait_for_dependencies(self, step: StepDefinition) -> None:
        """Wait for any declared dependencies (by step ID) before executing a step."""
        if not step.needs:
            return

        for dep_id in step.needs:
            # If dependency already completed and recorded, continue
            if self.session_context and self.session_context.state and dep_id in self.session_context.state.step_results:
                continue

            if dep_id not in self.session_tasks:
                raise ValueError(f"Dependency '{dep_id}' not found or not running")

            logger.info(f"Waiting for dependency '{dep_id}' to complete")
            task = self.session_tasks[dep_id]
            try:
                await task
            finally:
                # Leave the result in context; drop the handle so it doesn't pile up
                self.session_tasks.pop(dep_id, None)

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
            # If no condition is specified, default to success() - only run if no failures so far
            condition_to_evaluate = step.if_condition or "success()"

            logger.debug(f"Step '{step.id}': if_condition='{step.if_condition}', evaluating: '{condition_to_evaluate}'")

            step_results_dict = {}
            if self.session_context and self.session_context.state:
                step_results_dict = self.session_context.state.step_results

            evaluator = ConditionEvaluator(step_results_dict)
            should_run = evaluator.evaluate(condition_to_evaluate)

            if not should_run:
                logger.info(f"Skipping step '{step.id}' due to condition: {condition_to_evaluate}")
                # Record as skipped
                skipped_result = StepResult(
                    id=step.id or step.step,
                    name=step.step,
                    status=Status.SKIP,
                    duration=0.0,
                    result=None,
                    message=f"Skipped due to condition: {condition_to_evaluate}",
                )
                if self.session_context:
                    self.session_context.add_result(skipped_result)
                results.append({"id": step.id, "status": "skipped", "result": None, "message": f"Condition not met: {condition_to_evaluate}"})
                continue

            # Wait for declared dependencies (useful for background steps)
            await self._wait_for_dependencies(step)

            # Check if this step references a group
            if self._is_group_reference(step.step, scenario):
                # Handle loop execution for groups
                if step.loop:
                    loop_results = await self._execute_loop_for_group(step, scenario)
                    results.extend(loop_results)
                    if loop_results and any(r.get("status") == "error" for r in loop_results):
                        logger.error(f"Loop for group '{step.id}' failed, breaking scenario")
                        break
                else:
                    group_results = await self._execute_group(step, scenario)
                    results.extend(group_results)
                    if any(r.get("status") == "error" for r in group_results):
                        logger.error(f"Group '{step.id}' failed, breaking scenario")
                        break
            else:
                # Regular step execution
                # Handle loop execution
                if step.loop:
                    loop_results = await self._execute_loop(step)
                    results.extend(loop_results)
                    # Check if any loop iteration failed
                    if loop_results and any(r.get("status") == "error" for r in loop_results):
                        logger.error(f"Loop for step '{step.id}' failed, breaking scenario")
                        break
                else:
                    result = await self.execute_single_step(step)
                    results.append(result)
                    # Don't break on error - let conditions handle execution flow
                    # Steps with always() condition will still run after errors
        return results

    async def _execute_loop_for_group(self, step: StepDefinition, scenario: ScenarioDefinition) -> List[Dict[str, Any]]:
        """Execute a group multiple times based on loop configuration."""
        results = []
        loop_config = step.loop

        if not loop_config:
            return results

        # Determine loop iterations
        iterations = []
        if loop_config.count is not None:
            iterations = list(range(loop_config.count))
        elif loop_config.items is not None:
            iterations = loop_config.items

        if iterations:
            for index, item in enumerate(iterations):
                loop_context = {"index": index, "item": item if loop_config.items else index}

                # Check while condition if present
                if loop_config.while_condition:
                    step_results_dict = {}
                    if self.session_context and self.session_context.state:
                        step_results_dict = self.session_context.state.step_results

                    evaluator = ConditionEvaluator(step_results_dict, loop_context)
                    should_continue = evaluator.evaluate(loop_config.while_condition)
                    if not should_continue:
                        logger.info(f"Breaking loop for group '{step.id}' at iteration {index} due to while condition")
                        break

                logger.info(f"Executing loop iteration {index} for group '{step.id}'")
                group_results = await self._execute_group(step, scenario, loop_context)
                results.extend(group_results)

                if any(r.get("status") == "error" for r in group_results):
                    logger.error(f"Loop iteration {index} for group failed, breaking loop")
                    break

        return results

    async def _execute_loop(self, step: StepDefinition) -> List[Dict[str, Any]]:
        """Execute a step multiple times based on loop configuration."""
        results = []
        loop_config = step.loop

        if not loop_config:
            return results

        # Determine loop iterations
        iterations = []
        if loop_config.count is not None:
            # Fixed count loop
            iterations = list(range(loop_config.count))
        elif loop_config.items is not None:
            # Items loop
            iterations = loop_config.items
        else:
            # while loop - we'll handle separately
            pass

        if iterations:
            # Execute for each iteration
            for index, item in enumerate(iterations):
                loop_context = {"index": index, "item": item if loop_config.items else index}

                # Check if condition for continuing loop
                if loop_config.while_condition:
                    step_results_dict = {}
                    if self.session_context and self.session_context.state:
                        step_results_dict = self.session_context.state.step_results

                    evaluator = ConditionEvaluator(step_results_dict, loop_context)
                    should_continue = evaluator.evaluate(loop_config.while_condition)
                    if not should_continue:
                        logger.info(f"Breaking loop for step '{step.id}' at iteration {index} due to while condition")
                        break

                # Create a modified step with loop-aware ID
                loop_step = step.model_copy(deep=True)
                loop_step.id = f"{step.id}[{index}]"

                logger.info(f"Executing loop iteration {index} for step '{step.id}'")
                result = await self.execute_single_step(loop_step, loop_context)
                results.append(result)

                if result.get("status") == "error":
                    logger.error(f"Loop iteration {index} failed, breaking loop")
                    break

        elif loop_config.while_condition:
            # Pure while loop (no items, no count)
            index = 0
            max_iterations = 100  # Safety limit

            while index < max_iterations:
                step_results_dict = {}
                if self.session_context and self.session_context.state:
                    step_results_dict = self.session_context.state.step_results

                loop_context = {"index": index, "item": index}
                evaluator = ConditionEvaluator(step_results_dict, loop_context)
                should_continue = evaluator.evaluate(loop_config.while_condition)

                if not should_continue:
                    logger.info(f"Exiting while loop for step '{step.id}' at iteration {index}")
                    break

                loop_step = step.model_copy(deep=True)
                loop_step.id = f"{step.id}[{index}]"

                logger.info(f"Executing while loop iteration {index} for step '{step.id}'")
                result = await self.execute_single_step(loop_step, loop_context)
                results.append(result)

                if result.get("status") == "error":
                    logger.error(f"While loop iteration {index} failed, breaking loop")
                    break

                index += 1

            if index >= max_iterations:
                logger.warning(f"While loop for step '{step.id}' reached maximum iterations ({max_iterations})")

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
