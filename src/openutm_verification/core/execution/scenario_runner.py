import contextvars
import inspect
import time
from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    ParamSpec,
    Protocol,
    TypedDict,
    TypeVar,
    cast,
    overload,
)

from loguru import logger
from uas_standards.astm.f3411.v22a.api import RIDAircraftState

from openutm_verification.core.clients.opensky.base_client import OpenSkyError
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
class ScenarioState:
    steps: list[StepResult[Any]] = field(default_factory=list)
    active: bool = False
    flight_declaration_data: FlightDeclaration | None = None
    flight_declaration_via_operational_intent_data: FlightDeclarationViaOperationalIntent | None = None
    telemetry_data: list[RIDAircraftState] | None = None
    air_traffic_data: list[list[FlightObservationSchema]] = field(default_factory=list)


class ScenarioRegistry(TypedDict):
    func: Callable[..., Coroutine[Any, Any, ScenarioResult]]
    docs: Path | None


_scenario_state: contextvars.ContextVar[ScenarioState | None] = contextvars.ContextVar("scenario_state", default=None)


class ScenarioContext:
    def __init__(self):
        self._token = None
        self._state: ScenarioState | None = None

    def __enter__(self):
        self._state = ScenarioState(active=True)
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
            state.steps.append(result)

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


class StepDecorator(Protocol):
    @overload
    def __call__(self, func: Callable[P, Awaitable[R]]) -> Callable[P, Coroutine[Any, Any, R]]: ...

    @overload
    def __call__(self, func: Callable[P, Awaitable[T]]) -> Callable[P, Coroutine[Any, Any, StepResult[T]]]: ...

    def __call__(self, func: Callable[P, Awaitable[Any]]) -> Callable[P, Coroutine[Any, Any, Any]]: ...


def scenario_step(step_name: str) -> StepDecorator:
    def decorator(
        func: Callable[P, Awaitable[Any]],
    ) -> Callable[P, Coroutine[Any, Any, Any]]:
        def handle_result(result: Any, start_time: float) -> StepResult[Any]:
            duration = time.time() - start_time
            logger.info(f"Step '{step_name}' successful in {duration:.2f} seconds.")

            if isinstance(result, StepResult):
                step_result = result
            else:
                step_result = StepResult(
                    name=step_name,
                    status=Status.PASS,
                    duration=duration,
                    details=result,
                )

            ScenarioContext.add_result(step_result)
            return step_result

        def handle_exception(e: Exception, start_time: float) -> StepResult[Any]:
            duration = time.time() - start_time
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
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> StepResult[Any]:
            logger.info("-" * 50)
            logger.info(f"Executing step: '{step_name}'...")
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return handle_result(result, start_time)
            except Exception as e:
                return handle_exception(e, start_time)

        return async_wrapper

    return cast(StepDecorator, decorator)
