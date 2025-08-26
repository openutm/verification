import time
from functools import wraps

from loguru import logger

from .config_models import StepResult


def scenario_step(step_name):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info("-" * 50)
            logger.info(f"Executing step: '{step_name}'...")
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"Step '{step_name}' successful in {duration:.2f} seconds.")
                return StepResult(name=step_name, status="PASS", duration=duration, details=result)
            except Exception as e:
                duration = time.time() - start_time
                logger.error(f"Step '{step_name}' failed after {duration:.2f} seconds: {e}")
                return StepResult(
                    name=step_name,
                    status="FAIL",
                    duration=duration,
                    error_message=str(e),
                )

        return wrapper

    return decorator
