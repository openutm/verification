import contextvars
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, List, Optional

from loguru import logger

from openutm_verification.core.clients.opensky.base_client import OpenSkyError
from openutm_verification.core.reporting.reporting_models import Status, StepResult
from openutm_verification.models import FlightBlenderError


@dataclass
class ScenarioState:
    steps: List[StepResult] = field(default_factory=list)
    active: bool = False


_scenario_state: contextvars.ContextVar[Optional[ScenarioState]] = contextvars.ContextVar(
    "scenario_state", default=None
)


class ScenarioContext:
    def __init__(self):
        self._token = None
        self._state: Optional[ScenarioState] = None

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
    def add_result(cls, result: StepResult):
        state = _scenario_state.get()
        if state and state.active:
            state.steps.append(result)

    @property
    def steps(self) -> List[StepResult]:
        if self._state:
            return self._state.steps
        state = _scenario_state.get()
        return state.steps if state else []


def scenario_step(step_name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> StepResult:
            logger.info("-" * 50)
            logger.info(f"Executing step: '{step_name}'...")
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"Step '{step_name}' successful in {duration:.2f} seconds.")

                if isinstance(result, StepResult):
                    step_result = result
                else:
                    step_result = StepResult(name=step_name, status=Status.PASS, duration=duration, details=result)

                ScenarioContext.add_result(step_result)
                return step_result
            except (FlightBlenderError, OpenSkyError) as e:
                duration = time.time() - start_time
                logger.error(f"Step '{step_name}' failed after {duration:.2f} seconds: {e}")
                step_result = StepResult(
                    name=step_name,
                    status=Status.FAIL,
                    duration=duration,
                    error_message=str(e),
                )
                ScenarioContext.add_result(step_result)
                return step_result
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Step '{step_name}' encountered an unexpected error after {duration:.2f} seconds: {e}")
                step_result = StepResult(
                    name=step_name,
                    status=Status.FAIL,
                    duration=duration,
                    error_message=f"Unexpected error: {e}",
                )
                ScenarioContext.add_result(step_result)
                return step_result

        return wrapper

    return decorator
