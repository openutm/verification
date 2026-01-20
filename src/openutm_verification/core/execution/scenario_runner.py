import contextvars
import inspect
import time
import uuid
from asyncio import Queue
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    ParamSpec,
    TypedDict,
    TypeVar,
)

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, create_model
from uas_standards.astm.f3411.v22a.api import RIDAircraftState

from openutm_verification.core.clients.opensky.base_client import OpenSkyError
from openutm_verification.core.execution.dependency_resolution import DEPENDENCIES
from openutm_verification.core.reporting.reporting_models import (
    ScenarioResult,
    Status,
    StepResult,
)
from openutm_verification.models import FlightBlenderError
from openutm_verification.simulator.models.declaration_models import (
    FlightDeclaration,
    FlightDeclarationViaOperationalIntent,
)
from openutm_verification.simulator.models.flight_data_types import (
    FlightObservationSchema,
)

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R", bound=StepResult[Any])


@dataclass
class StepRegistryEntry:
    client_class: type
    method_name: str
    param_model: type[BaseModel]


@dataclass
class ScenarioState:
    steps: list[StepResult[Any]] = field(default_factory=list)
    active: bool = False
    flight_declaration_data: FlightDeclaration | None = None
    flight_declaration_via_operational_intent_data: FlightDeclarationViaOperationalIntent | None = None
    telemetry_data: list[RIDAircraftState] | None = None
    air_traffic_data: list[list[FlightObservationSchema]] = field(default_factory=list)
    added_results: Queue[StepResult[Any]] = field(default_factory=Queue)

    @property
    def step_results(self) -> dict[str, StepResult[Any]]:
        """
        Returns a dictionary mapping step IDs to their result details.
        Only includes steps that have an ID.
        """
        return {step.id: step for step in self.steps if step.id}


class ScenarioRegistry(TypedDict):
    func: Callable[..., Coroutine[Any, Any, ScenarioResult]]
    docs: Path | None


class RefModel(BaseModel, serialize_by_alias=True):
    ref: str = Field(..., alias="$ref")


_scenario_state: contextvars.ContextVar[ScenarioState | None] = contextvars.ContextVar("scenario_state", default=None)

STEP_REGISTRY: dict[str, StepRegistryEntry] = {}


class ScenarioContext:
    def __init__(self, state: ScenarioState | None = None):
        self._token = None
        self._state: ScenarioState | None = state

    def __enter__(self):
        if self._state is None:
            self._state = ScenarioState(active=True)
        else:
            self._state.active = True
        self._token = _scenario_state.set(self._state)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._state:
            self._state.active = False
        if self._token:
            _scenario_state.reset(self._token)

    @classmethod
    def add_result(cls, result: StepResult[Any]) -> None:
        state = _scenario_state.get()
        if state and state.active:
            if result.id and state.step_results.get(result.id):
                state.steps.remove(state.step_results[result.id])
            state.steps.append(result)
            state.added_results.put_nowait(result)

    @classmethod
    def set_flight_declaration_data(cls, data: FlightDeclaration) -> None:
        state = _scenario_state.get()
        if state and state.active:
            state.flight_declaration_data = data

    @classmethod
    def set_flight_declaration_via_operational_intent_data(cls, data: FlightDeclarationViaOperationalIntent) -> None:
        state = _scenario_state.get()
        if state and state.active:
            state.flight_declaration_via_operational_intent_data = data

    @classmethod
    def set_telemetry_data(cls, data: list[RIDAircraftState]) -> None:
        state = _scenario_state.get()
        if state and state.active:
            state.telemetry_data = data

    @classmethod
    def add_air_traffic_data(cls, data: list[FlightObservationSchema]) -> None:
        state = _scenario_state.get()
        if state and state.active:
            state.air_traffic_data.append(data)

    @property
    def state(self) -> ScenarioState | None:
        return self._state

    @property
    def steps(self) -> list[StepResult[Any]]:
        if self._state:
            return self._state.steps
        state = _scenario_state.get()
        return state.steps if state else []

    @property
    def flight_declaration_data(self) -> FlightDeclaration | None:
        if self._state:
            return self._state.flight_declaration_data
        state = _scenario_state.get()
        return state.flight_declaration_data if state else None

    @property
    def flight_declaration_via_operational_intent_data(
        self,
    ) -> FlightDeclarationViaOperationalIntent | None:
        if self._state:
            return self._state.flight_declaration_via_operational_intent_data
        state = _scenario_state.get()
        return state.flight_declaration_via_operational_intent_data if state else None

    @property
    def telemetry_data(self) -> list[RIDAircraftState] | None:
        if self._state:
            return self._state.telemetry_data
        state = _scenario_state.get()
        return state.telemetry_data if state else None

    @property
    def air_traffic_data(self) -> list[list[FlightObservationSchema]]:
        if self._state:
            return self._state.air_traffic_data
        state = _scenario_state.get()
        return state.air_traffic_data if state else []


class ScenarioStepDescriptor:
    def __init__(self, func: Callable[..., Awaitable[Any]], step_name: str):
        self.func = func
        self.step_name = step_name
        self.wrapper = self._create_wrapper(func, step_name)
        self.param_model = self._create_param_model(func, step_name)

    def _create_param_model(self, func: Callable[..., Any], step_name: str) -> type[BaseModel]:
        sig = inspect.signature(func)
        fields = {}

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            # Skip dependencies that are automatically injected
            if param.annotation in DEPENDENCIES:
                continue

            annotation = param.annotation
            if annotation == inspect.Parameter.empty:
                annotation = Any

            default = param.default
            if default == inspect.Parameter.empty:
                fields[param_name] = (annotation, ...)
            else:
                fields[param_name] = (annotation, default)

        return create_model(  # type: ignore[call-overload]
            f"Params_{step_name}",
            __config__=ConfigDict(arbitrary_types_allowed=True),
            **fields,
        )

    def _create_wrapper(self, func: Callable[..., Awaitable[Any]], step_name: str) -> Callable[..., Awaitable[Any]]:
        def handle_result(result: Any, start_time: float) -> StepResult[Any]:
            duration = time.time() - start_time
            logger.info(f"Step '{step_name}' successful in {duration:.2f} seconds.")

            step_result: StepResult[Any]
            if isinstance(result, StepResult):
                step_result = result
            else:
                step_result = StepResult(
                    name=step_name,
                    status=Status.PASS,
                    duration=duration,
                    result=result,
                )

            ScenarioContext.add_result(step_result)
            return step_result

        def handle_exception(e: Exception, start_time: float) -> StepResult[Any]:
            duration = time.time() - start_time
            step_result: StepResult[Any]
            if isinstance(e, (FlightBlenderError, OpenSkyError)):
                logger.error(f"Step '{step_name}' failed after {duration:.2f} seconds: {e}")
                step_result = StepResult(
                    name=step_name,
                    status=Status.FAIL,
                    duration=duration,
                    error_message=str(e),
                )
            else:
                logger.error(f"Step '{step_name}' encountered an unexpected error after {duration:.2f} seconds: {e}")
                step_result = StepResult(
                    name=step_name,
                    status=Status.FAIL,
                    duration=duration,
                    error_message=f"Unexpected error: {e}",
                )
            ScenarioContext.add_result(step_result)
            return step_result

        if not inspect.iscoroutinefunction(func):
            raise ValueError(f"Step function {func.__name__} must be async")

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> StepResult[Any]:
            step_execution_id = uuid.uuid4().hex
            captured_logs: list[str] = []

            def log_filter(record):
                return record["extra"].get("step_execution_id") == step_execution_id

            handler_id = logger.add(lambda msg: captured_logs.append(msg), filter=log_filter, format="{time:HH:mm:ss} | {level} | {message}")

            step_result: StepResult[Any]
            try:
                with logger.contextualize(step_execution_id=step_execution_id):
                    logger.info("-" * 50)
                    logger.info(f"Executing step: '{step_name}'...")
                    start_time = time.time()
                    try:
                        result = await func(*args, **kwargs)
                        step_result = handle_result(result, start_time)
                    except Exception as e:
                        step_result = handle_exception(e, start_time)
            finally:
                logger.remove(handler_id)
                if step_result:
                    step_result.logs = captured_logs

            return step_result

        # Attach metadata for introspection
        setattr(async_wrapper, "_is_scenario_step", True)
        setattr(async_wrapper, "_step_name", step_name)

        return async_wrapper

    def __set_name__(self, owner: type, name: str):
        # Register using the human-readable step name
        registry_key = self.step_name
        if registry_key in STEP_REGISTRY:
            logger.warning(f"Overwriting step registry for '{registry_key}'. Ensure step names are unique.")

        STEP_REGISTRY[registry_key] = StepRegistryEntry(
            client_class=owner,
            method_name=name,
            param_model=self.param_model,
        )
        setattr(owner, name, self.wrapper)

    def __call__(self, *args: Any, **kwargs: Any):
        return self.wrapper(*args, **kwargs)


def scenario_step(step_name: str) -> Callable[[Callable[..., Awaitable[Any]]], Any]:
    def decorator(func: Callable[..., Awaitable[Any]]) -> Any:
        return ScenarioStepDescriptor(func, step_name)

    return decorator
