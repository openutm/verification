"""Condition evaluation for step execution.

Supports GitHub Actions-style conditions:
- success(): Previous step succeeded
- failure(): Previous step failed
- always(): Always run (regardless of previous steps)
- steps.<step_id>.result: Access step results
- Comparison operators: ==, !=, <, >, <=, >=
- Logical operators: &&, ||
- String literals: 'value' or \"value\"
"""

import re
from typing import Any

from loguru import logger

from openutm_verification.core.reporting.reporting_models import Status, StepResult


class ConditionEvaluator:
    """Evaluates conditional expressions for step execution."""

    def __init__(self, steps: dict[str, StepResult[Any]]):
        """Initialize evaluator with step results.

        Args:
            steps: Dictionary mapping step IDs to their results
        """
        self.steps = steps
        self.last_step_status: Status | None = None

        # Determine last step status (excluding skipped steps)
        if steps:
            completed_steps = [s for s in steps.values() if s.status != Status.SKIP]
            if completed_steps:
                self.last_step_status = completed_steps[-1].status

    def evaluate(self, condition: str) -> bool:
        """Evaluate a condition string.

        Args:
            condition: Condition expression to evaluate

        Returns:
            True if condition passes, False otherwise
        """
        if not condition or not condition.strip():
            return True

        try:
            # Replace function calls
            condition = self._replace_functions(condition)

            # Replace step references
            condition = self._replace_step_references(condition)

            # Evaluate the expression
            result = self._evaluate_expression(condition)
            logger.debug(f"Condition '{condition}' evaluated to {result}")
            return result

        except Exception as e:
            logger.warning(f"Error evaluating condition '{condition}': {e}")
            return False

    def _replace_functions(self, condition: str) -> str:
        """Replace GitHub Actions-style functions."""
        # success() - previous step succeeded
        if "success()" in condition:
            result = self.last_step_status == Status.PASS if self.last_step_status else True
            condition = condition.replace("success()", str(result))

        # failure() - previous step failed
        if "failure()" in condition:
            result = self.last_step_status == Status.FAIL if self.last_step_status else False
            condition = condition.replace("failure()", str(result))

        # always() - always run
        if "always()" in condition:
            condition = condition.replace("always()", "True")

        return condition

    def _replace_step_references(self, condition: str) -> str:
        """Replace step.X.Y references with actual values."""
        # Pattern: steps.<step_id>.status or steps.<step_id>.result
        pattern = r"steps\.([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_]+)"

        def replace_match(match: re.Match) -> str:
            step_id = match.group(1)
            field = match.group(2)

            if step_id not in self.steps:
                logger.warning(f"Step '{step_id}' not found in results")
                return "None"

            step = self.steps[step_id]

            if field == "status":
                # Return status as string for comparison
                return f"'{step.status.value}'"
            elif field == "result":
                # Return result value (could be complex, so use repr for safety)
                return repr(step.result)
            else:
                logger.warning(f"Unknown field '{field}' for step '{step_id}'")
                return "None"

        return re.sub(pattern, replace_match, condition)

    def _evaluate_expression(self, expr: str) -> bool:
        """Safely evaluate a boolean expression.

        Supports:
        - Comparison operators: ==, !=, <, >, <=, >=
        - Logical operators: &&, ||, !
        - Boolean literals: True, False
        - String literals: 'value'
        """
        # Replace logical operators with Python equivalents
        expr = expr.replace("&&", " and ").replace("||", " or ").replace("!", " not ")

        # Only allow safe evaluation
        # Create a restricted namespace
        namespace = {"True": True, "False": False, "None": None, "__builtins__": {}}

        try:
            result = eval(expr, namespace, {})
            return bool(result)
        except Exception as e:
            logger.error(f"Failed to evaluate expression '{expr}': {e}")
            return False
