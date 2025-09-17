import time
from functools import wraps
from typing import Any, Callable

from loguru import logger

from openutm_verification.core.clients.opensky.base_client import OpenSkyError

from ...models import FlightBlenderError
from ..reporting.reporting_models import Status, StepResult


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
                return StepResult(name=step_name, status=Status.PASS, duration=duration, details=result)
            except (FlightBlenderError, OpenSkyError) as e:
                duration = time.time() - start_time
                logger.error(f"Step '{step_name}' failed after {duration:.2f} seconds: {e}")
                return StepResult(
                    name=step_name,
                    status=Status.FAIL,
                    duration=duration,
                    error_message=str(e),
                )
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Step '{step_name}' encountered an unexpected error after {duration:.2f} seconds: {e}")
                return StepResult(
                    name=step_name,
                    status=Status.FAIL,
                    duration=duration,
                    error_message=f"Unexpected error: {e}",
                )

        return wrapper

    return decorator
