import asyncio
import os
import re
from contextlib import AsyncExitStack
from datetime import datetime, timezone
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
from openutm_verification.core.reporting.reporting import get_run_timestamp_str
from openutm_verification.core.reporting.reporting_models import Status, StepResult
from openutm_verification.scenarios.common import generate_flight_declaration, generate_telemetry
from openutm_verification.server.introspection import process_method
from openutm_verification.utils.logging import setup_logging

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
        self.current_run_task: asyncio.Task | None = None
        self.current_run_error: str | None = None
        self.current_output_dir: Path | None = None
        self.current_timestamp_str: str | None = None
        self.current_start_time: datetime | None = None
        self._initialized = True

    async def start_scenario_task(self, scenario: ScenarioDefinition):
        if not self.session_resolver:
            await self.initialize_session()

        if self.current_run_task and not self.current_run_task.done():
            self.current_run_task.cancel()

        self.current_run_error = None

        task = asyncio.create_task(self.run_scenario(scenario))
        self.current_run_task = task

        def _on_done(t: asyncio.Task) -> None:
            try:
                t.result()
            except asyncio.CancelledError:
                # Task was cancelled (e.g., by stop_scenario), error is already set there
                pass
            except Exception as exc:  # noqa: BLE001
                self.current_run_error = str(exc)

        task.add_done_callback(_on_done)

    def get_run_status(self) -> Dict[str, Any]:
        status = "running"
        if self.current_run_task and self.current_run_task.done():
            status = "error" if self.current_run_error else "completed"

        return {
            "status": status,
            "error": self.current_run_error,
        }

    async def stop_scenario(self) -> bool:
        """Stop the currently running scenario and all background tasks."""
        logger.info("Stopping scenario...")
        stopped = False
        tasks_to_cancel = []

        # Cancel the main scenario task
        if self.current_run_task and not self.current_run_task.done():
            self.current_run_task.cancel()
            tasks_to_cancel.append(self.current_run_task)
            stopped = True

        # Cancel all background tasks
        for task in self.session_tasks.values():
            if not task.done():
                task.cancel()
                tasks_to_cancel.append(task)
                stopped = True

        # Wait for all tasks to actually be cancelled (with timeout)
        if tasks_to_cancel:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks_to_cancel, return_exceptions=True), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for tasks to cancel")

        if stopped:
            self.current_run_error = "Scenario stopped by user"
            logger.info("Scenario stopped by user")

        return stopped

    def has_pending_tasks(self) -> bool:
        """Check if any background tasks are still running."""
        return any(not task.done() for task in self.session_tasks.values())

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

        if not self.session_context or not self.session_context.state:
            raise ValueError("No active scenario context or state available")

        state = self.session_context.state

        step_result: Any | None = None

        # When inside a group context, check group_context FIRST for the most recent results
        # This is important because state.step_results may have stale RUNNING entries
        if loop_context and "group_context" in loop_context:
            group_context = loop_context["group_context"]
            if step_name in group_context:
                step_result = group_context[step_name]
        # Fall back to state.step_results if not found in group_context
        if step_result is None:
            if step_name in state.step_results:
                step_result = state.step_results[step_name]
            else:
                # Try matching by suffix (for looped step IDs like "group[0].step_name")
                matching_ids = [key for key in state.step_results.keys() if key.endswith(f".{step_name}") or key == step_name]
                if matching_ids:
                    step_result = state.step_results[matching_ids[-1]]

        if step_result is None:
            logger.error(f"Step '{step_name}' not found in results. Available steps: {list(state.step_results.keys())}")
            raise ValueError(f"Referenced step '{step_name}' not found in results")

        # Start traversing from the step result object
        current_value = step_result

        # Skip "steps" and "step_name"
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
                    self.session_context.update_result(res)
                    return

                result_data = self._serialize_result(res)
                status_str = self._determine_status(res)
                status = Status.PASS if status_str == "success" else Status.FAIL
                self.session_context.update_result(StepResult(id=step_id, name=step_name, status=status, result=result_data, duration=0.0))
            except asyncio.CancelledError:
                # Task was cancelled, possibly due to server shutdown or stop request
                pass
            except Exception as exc:  # noqa: BLE001
                self.session_context.update_result(StepResult(id=step_id, name=step_name, status=Status.FAIL, error_message=str(exc), duration=0.0))

        task.add_done_callback(_on_done)

    async def _record_step_running(self, step: StepDefinition, task_id: Any = None) -> StepResult:
        assert self.session_context is not None
        result = StepResult(
            id=step.id or step.step,
            name=step.step,
            status=Status.RUNNING,
            duration=0.0,
            result={"task_id": task_id} if task_id is not None else None,
        )
        self.session_context.update_result(result)
        return result

    async def _execute_step(self, step: StepDefinition, loop_context: Dict[str, Any] | None = None) -> StepResult:
        assert self.session_resolver is not None and self.session_context is not None
        if step.step not in STEP_REGISTRY:
            raise ValueError(f"Step '{step.step}' not found in registry")

        entry = STEP_REGISTRY[step.step]
        client = await self.session_resolver.resolve(entry.client_class)

        method = getattr(client, entry.method_name)

        # Prepare parameters (resolve refs, inject context)
        try:
            kwargs = self._prepare_params(step, loop_context)
        except Exception as e:
            step_id = step.id or step.step
            logger.error(f"Failed to prepare parameters for step '{step_id}': {e}")
            result = StepResult(
                id=step_id,
                name=step.step,
                status=Status.FAIL,
                error_message=f"Parameter resolution failed: {e}",
                duration=0.0,
            )
            self.session_context.update_result(result)
            return result

        if step.background:
            step_id = step.id or step.step
            logger.info(f"Executing step '{step_id}' ({step.step}) in background")
            task = asyncio.create_task(call_with_dependencies(method, resolver=self.session_resolver, **kwargs))
            self.session_tasks[step_id] = task
            self._record_background_result(step_id, step.step, task)
            return await self._record_step_running(step, task_id=step_id)
        await self._record_step_running(step)
        step_id = step.id or step.step

        # Execute with dependencies
        try:
            result = await call_with_dependencies(method, resolver=self.session_resolver, **kwargs)
        except Exception as e:
            logger.error(f"Step '{step_id}' execution failed: {e}")
            failed_result = StepResult(
                id=step_id,
                name=step.step,
                status=Status.FAIL,
                error_message=str(e),
                duration=0.0,
            )
            self.session_context.update_result(failed_result)
            return failed_result

        # If result is a StepResult and we have a step ID, update the ID in the result object
        # This updates the object in state.steps as well since it's the same reference
        if step.id and hasattr(result, "id"):
            result.id = step.id
        # Add result to context
        logger.info(f"Adding result for step '{step_id}' (name: {step.step}) to context")

        # If the result is already a StepResult (from scenario_step decorator), use it directly but ensure ID is correct
        if isinstance(result, StepResult):
            result.id = step_id
            self.session_context.update_result(result)
            return result

        step_result = StepResult(id=step_id, name=step.step, status=Status.PASS, result=result, duration=0.0)
        self.session_context.update_result(step_result)
        return step_result

    async def execute_single_step(self, step: StepDefinition, loop_context: Dict[str, Any] | None = None) -> StepResult:
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
            # Update step status to FAIL before re-raising
            if self.session_context:
                with self.session_context:
                    failed_result = StepResult(
                        id=step_id,
                        name=step.step,
                        status=Status.FAIL,
                        error_message=str(e),
                        duration=0.0,
                    )
                    self.session_context.update_result(failed_result)
            raise

    def _is_group_reference(self, step_name: str, scenario: ScenarioDefinition) -> bool:
        """Check if a step name references a group."""
        return step_name in scenario.groups

    async def _execute_group(
        self, step: StepDefinition, scenario: ScenarioDefinition, loop_context: Dict[str, Any] | None = None
    ) -> List[StepResult]:
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

        # Pre-compute step IDs with loop index
        # Note: We don't pre-record as RUNNING here because _execute_step will do it
        step_id_map: Dict[int, str] = {}
        for idx, grp_step in enumerate(group.steps):
            original_id = grp_step.id or grp_step.step
            if loop_context and "index" in loop_context:
                loop_index = loop_context.get("index")
                step_id_map[idx] = f"{group_name}[{loop_index}].{original_id}"
            else:
                step_id_map[idx] = original_id

        executed_step_indices: set[int] = set()

        for idx, group_step in enumerate(group.steps):
            # Ensure each step has an ID
            if not group_step.id:
                group_step.id = group_step.step

            original_id = group_step.id
            exec_step = group_step.model_copy(deep=True)
            exec_step.id = step_id_map[idx]

            # Evaluate condition if present for group step
            if group_step.if_condition:
                step_results_dict = {}
                if self.session_context and self.session_context.state:
                    step_results_dict = self.session_context.state.step_results.copy()
                # Add group context results for condition evaluation
                for gid, gresult in group_context.items():
                    step_results_dict[gid] = gresult

                evaluator = ConditionEvaluator(step_results_dict, enhanced_loop_context)
                should_run = evaluator.evaluate(group_step.if_condition)

                if not should_run:
                    logger.info(f"Skipping group step '{exec_step.id}' due to condition: {group_step.if_condition}")
                    skipped_result = StepResult(
                        id=exec_step.id,
                        name=exec_step.step,
                        status=Status.SKIP,
                        duration=0.0,
                        error_message=f"Skipped due to condition: {group_step.if_condition}",
                    )
                    results.append(skipped_result)
                    executed_step_indices.add(idx)
                    if self.session_context:
                        with self.session_context:
                            self.session_context.update_result(skipped_result)
                    group_context[original_id] = skipped_result
                    continue

            # Execute the step with the enhanced context
            result = await self.execute_single_step(exec_step, enhanced_loop_context)
            results.append(result)
            executed_step_indices.add(idx)

            # Store result in group context for subsequent steps
            # Store the entire result dict so nested access works (group.step_id.result)
            group_context[original_id] = result

            # If step failed and it's not allowed to fail, break the group
            if result.status == Status.FAIL:
                logger.error(f"Group step '{group_step.id}' failed, stopping group execution")
                # Mark remaining steps as SKIP
                self._mark_remaining_group_steps_skipped(group, group_name, loop_context, executed_step_indices)
                break

        return results

    def _mark_remaining_group_steps_skipped(
        self,
        group: Any,
        group_name: str,
        loop_context: Dict[str, Any] | None,
        executed_step_indices: set[int],
    ) -> None:
        """Mark remaining group steps as SKIP after a failure."""
        if not self.session_context:
            return

        for idx, remaining_step in enumerate(group.steps):
            if idx in executed_step_indices:
                continue  # Already executed

            step_id = remaining_step.id or remaining_step.step
            if loop_context and "index" in loop_context:
                loop_index = loop_context.get("index")
                step_id = f"{group_name}[{loop_index}].{step_id}"

            skipped_result = StepResult(
                id=step_id,
                name=remaining_step.step,
                status=Status.SKIP,
                duration=0.0,
                error_message="Skipped due to previous step failure",
            )
            with self.session_context:
                self.session_context.update_result(skipped_result)

    async def _wait_for_dependencies(self, step: StepDefinition) -> None:
        """Wait for any declared dependencies (by step ID) before executing a step."""
        if not step.needs:
            return

        for dep_id in step.needs:
            # If dependency already completed and recorded, continue ONLY if not RUNNING
            if self.session_context and self.session_context.state and dep_id in self.session_context.state.step_results:
                # Check status
                if self.session_context.state.step_results[dep_id].status != Status.RUNNING:
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

    async def run_scenario(self, scenario: ScenarioDefinition) -> List[StepResult]:
        if not self.session_resolver:
            await self.initialize_session()

        # Set up logging to file for this run
        run_timestamp = datetime.now(timezone.utc)
        self.current_start_time = run_timestamp
        self.current_timestamp_str = get_run_timestamp_str(run_timestamp)
        base_output_dir = Path(self.config.reporting.output_dir)
        self.current_output_dir = base_output_dir / self.current_timestamp_str
        self.current_output_dir.mkdir(parents=True, exist_ok=True)

        log_file = setup_logging(
            self.current_output_dir,
            "report",
            self.config.reporting.formats,
            debug=False,
        )
        if log_file:
            logger.info(f"Logging to file: {log_file}")

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
                    error_message=f"Skipped due to condition: {condition_to_evaluate}",
                )
                if self.session_context:
                    with self.session_context:
                        self.session_context.update_result(skipped_result)
                continue

            # Wait for declared dependencies (useful for background steps)
            await self._wait_for_dependencies(step)

            # Check if this step references a group
            if self._is_group_reference(step.step, scenario):
                # Handle loop execution for groups
                if step.loop:
                    loop_results = await self._execute_loop_for_group(step, scenario)
                    if loop_results and any(r.status == Status.FAIL for r in loop_results):
                        logger.error(f"Loop for group '{step.id}' failed, breaking scenario")
                        break
                else:
                    group_results = await self._execute_group(step, scenario)
                    if any(r.status == Status.FAIL for r in group_results):
                        logger.error(f"Group '{step.id}' failed, breaking scenario")
                        break
            else:
                # Regular step execution
                # Handle loop execution
                if step.loop:
                    loop_results = await self._execute_loop(step)
                    # Check if any loop iteration failed
                    if loop_results and any(r.status == Status.FAIL for r in loop_results):
                        logger.error(f"Loop for step '{step.id}' failed, breaking scenario")
                        break
                else:
                    await self.execute_single_step(step)
        return self.session_context.state.steps

    async def _execute_loop_for_group(self, step: StepDefinition, scenario: ScenarioDefinition) -> List[StepResult]:
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

                if any(r.status == Status.FAIL for r in group_results):
                    logger.error(f"Loop iteration {index} for group failed, breaking loop")
                    break

        return results

    async def _execute_loop(self, step: StepDefinition) -> List[StepResult]:
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

                if result.status == Status.FAIL:
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

                if result.status == Status.FAIL:
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
