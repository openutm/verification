"""Tests for conditional execution and loop features."""

from openutm_verification.core.execution.conditions import ConditionEvaluator
from openutm_verification.core.reporting.reporting_models import Status, StepResult


class TestConditionEvaluator:
    """Test the ConditionEvaluator class."""

    def test_success_function_with_all_passed(self):
        """Test success() returns True when all steps passed."""
        steps = {
            "step1": StepResult(id="step1", name="Step 1", status=Status.PASS, duration=1.0),
            "step2": StepResult(id="step2", name="Step 2", status=Status.PASS, duration=1.0),
        }
        evaluator = ConditionEvaluator(steps)
        assert evaluator.evaluate("success()") is True

    def test_success_function_with_failure(self):
        """Test success() returns False when any step failed."""
        steps = {
            "step1": StepResult(id="step1", name="Step 1", status=Status.PASS, duration=1.0),
            "step2": StepResult(id="step2", name="Step 2", status=Status.FAIL, duration=1.0),
        }
        evaluator = ConditionEvaluator(steps)
        assert evaluator.evaluate("success()") is False

    def test_success_function_ignores_skipped(self):
        """Test success() ignores skipped steps."""
        steps = {
            "step1": StepResult(id="step1", name="Step 1", status=Status.PASS, duration=1.0),
            "step2": StepResult(id="step2", name="Step 2", status=Status.SKIP, duration=0.0),
        }
        evaluator = ConditionEvaluator(steps)
        assert evaluator.evaluate("success()") is True

    def test_failure_function_with_failure(self):
        """Test failure() returns True when any step failed."""
        steps = {
            "step1": StepResult(id="step1", name="Step 1", status=Status.PASS, duration=1.0),
            "step2": StepResult(id="step2", name="Step 2", status=Status.FAIL, duration=1.0),
        }
        evaluator = ConditionEvaluator(steps)
        assert evaluator.evaluate("failure()") is True

    def test_failure_function_with_all_passed(self):
        """Test failure() returns False when all steps passed."""
        steps = {
            "step1": StepResult(id="step1", name="Step 1", status=Status.PASS, duration=1.0),
            "step2": StepResult(id="step2", name="Step 2", status=Status.PASS, duration=1.0),
        }
        evaluator = ConditionEvaluator(steps)
        assert evaluator.evaluate("failure()") is False

    def test_always_function(self):
        """Test always() always returns True."""
        steps = {
            "step1": StepResult(id="step1", name="Step 1", status=Status.FAIL, duration=1.0),
        }
        evaluator = ConditionEvaluator(steps)
        assert evaluator.evaluate("always()") is True

    def test_step_status_check(self):
        """Test checking specific step status."""
        steps = {
            "step1": StepResult(id="step1", name="Step 1", status=Status.PASS, duration=1.0),
            "step2": StepResult(id="step2", name="Step 2", status=Status.FAIL, duration=1.0),
        }
        evaluator = ConditionEvaluator(steps)
        assert evaluator.evaluate("steps.step1.status == 'success'") is True
        assert evaluator.evaluate("steps.step2.status == 'success'") is False
        assert evaluator.evaluate("steps.step2.status == 'failure'") is True

    def test_step_result_check(self):
        """Test accessing step result values."""
        steps = {
            "step1": StepResult(id="step1", name="Step 1", status=Status.PASS, duration=1.0, details={"data": "value"}),
        }
        evaluator = ConditionEvaluator(steps)
        assert evaluator.evaluate("steps.step1.result != None") is True

    def test_complex_condition_with_and(self):
        """Test complex condition with AND operator."""
        steps = {
            "step1": StepResult(id="step1", name="Step 1", status=Status.PASS, duration=1.0),
            "step2": StepResult(id="step2", name="Step 2", status=Status.PASS, duration=1.0),
        }
        evaluator = ConditionEvaluator(steps)
        assert evaluator.evaluate("success() && steps.step1.status == 'success'") is True
        assert evaluator.evaluate("success() && steps.step1.status == 'failure'") is False

    def test_complex_condition_with_or(self):
        """Test complex condition with OR operator."""
        steps = {
            "step1": StepResult(id="step1", name="Step 1", status=Status.FAIL, duration=1.0),
            "step2": StepResult(id="step2", name="Step 2", status=Status.PASS, duration=1.0),
        }
        evaluator = ConditionEvaluator(steps)
        assert evaluator.evaluate("failure() || steps.step2.status == 'success'") is True
        assert evaluator.evaluate("success() || steps.step2.status == 'success'") is True

    def test_condition_with_not(self):
        """Test condition with NOT operator."""
        steps = {
            "step1": StepResult(id="step1", name="Step 1", status=Status.SKIP, duration=0.0),
        }
        evaluator = ConditionEvaluator(steps)
        assert evaluator.evaluate("steps.step1.status != 'skipped'") is False
        assert evaluator.evaluate("not steps.step1.status == 'skipped'") is False

    def test_empty_condition_returns_true(self):
        """Test that empty condition defaults to True."""
        evaluator = ConditionEvaluator({})
        assert evaluator.evaluate("") is True
        assert evaluator.evaluate("   ") is True

    def test_unknown_step_reference(self):
        """Test referencing unknown step returns False."""
        steps = {
            "step1": StepResult(id="step1", name="Step 1", status=Status.PASS, duration=1.0),
        }
        evaluator = ConditionEvaluator(steps)
        # Should not raise, but return False due to warning and None replacement
        result = evaluator.evaluate("steps.unknown_step.status == 'success'")
        assert result is False

    def test_loop_index_in_condition(self):
        """Test using loop.index in condition."""
        steps = {}
        loop_context = {"index": 5, "item": "test"}
        evaluator = ConditionEvaluator(steps, loop_context)
        assert evaluator.evaluate("loop.index < 10") is True
        assert evaluator.evaluate("loop.index > 10") is False
        assert evaluator.evaluate("loop.index == 5") is True

    def test_loop_item_in_condition(self):
        """Test using loop.item in condition."""
        steps = {}
        loop_context = {"index": 0, "item": "ACTIVATED"}
        evaluator = ConditionEvaluator(steps, loop_context)
        assert evaluator.evaluate("loop.item == 'ACTIVATED'") is True
        assert evaluator.evaluate("loop.item == 'ENDED'") is False

    def test_loop_context_with_numeric_item(self):
        """Test loop.item with numeric value."""
        steps = {}
        loop_context = {"index": 2, "item": 42}
        evaluator = ConditionEvaluator(steps, loop_context)
        assert evaluator.evaluate("loop.item == 42") is True
        assert evaluator.evaluate("loop.item > 40") is True

    def test_combined_step_and_loop_conditions(self):
        """Test combining step status checks with loop variables."""
        steps = {
            "step1": StepResult(id="step1", name="Step 1", status=Status.PASS, duration=1.0),
        }
        loop_context = {"index": 3, "item": "value"}
        evaluator = ConditionEvaluator(steps, loop_context)
        assert evaluator.evaluate("success() && loop.index < 5") is True
        assert evaluator.evaluate("steps.step1.status == 'success' && loop.index > 2") is True

    def test_loop_index_boundary_conditions(self):
        """Test loop.index at boundaries."""
        steps = {}
        loop_context = {"index": 0, "item": "first"}
        evaluator = ConditionEvaluator(steps, loop_context)
        assert evaluator.evaluate("loop.index == 0") is True
        assert evaluator.evaluate("loop.index > 0") is False

        loop_context = {"index": 99, "item": "last"}
        evaluator = ConditionEvaluator(steps, loop_context)
        assert evaluator.evaluate("loop.index < 100") is True
        assert evaluator.evaluate("loop.index >= 99") is True
