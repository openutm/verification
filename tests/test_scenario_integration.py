"""Integration tests for conditional execution and loops in scenarios."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openutm_verification.core.execution.definitions import LoopConfig, ScenarioDefinition, StepDefinition
from openutm_verification.core.execution.scenario_runner import ScenarioContext, ScenarioState
from openutm_verification.core.reporting.reporting_models import Status, StepResult
from openutm_verification.server.runner import SessionManager


@pytest.fixture
def session_manager():
    """Create a SessionManager instance for testing with mocked session context."""
    manager = SessionManager()
    # Create a real ScenarioContext with state for testing
    state = ScenarioState(active=True)
    manager.session_context = ScenarioContext(state=state)
    # Mark resolver as initialized to skip initialize_session call
    manager.session_resolver = MagicMock()
    # Mock session_stack with async aclose method
    manager.session_stack = MagicMock()
    manager.session_stack.aclose = AsyncMock()
    # Mock initialize_session and close_session to avoid actual session management
    manager.initialize_session = AsyncMock()
    manager.close_session = AsyncMock()
    return manager


class TestScenarioWithConditions:
    """Integration tests for scenarios with conditional execution."""

    @pytest.mark.asyncio
    async def test_success_condition_execution(self, session_manager):
        """Test that steps with success() condition run when previous steps succeed."""
        scenario = ScenarioDefinition(
            name="Test Conditional",
            description="Test success condition",
            steps=[
                StepDefinition(id="step1", step="Setup Flight Declaration", arguments={}),
                StepDefinition(id="step2", step="Submit Telemetry", arguments={"duration": 10}, if_condition="success()"),
            ],
        )

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:

            async def mock_execute_step(step, loop_context=None):
                step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
                if session_manager.session_context:
                    with session_manager.session_context:
                        session_manager.session_context.add_result(step_result)
                return step_result

            mock_execute.side_effect = mock_execute_step

            results = await session_manager.run_scenario(scenario)

            # Both steps should execute
            assert len([r for r in results if r.status != Status.RUNNING]) == 2
            assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    async def test_failure_condition_skips_on_success(self, session_manager):
        """Test that steps with failure() condition are skipped when all succeed."""
        scenario = ScenarioDefinition(
            name="Test Conditional",
            description="Test failure condition",
            steps=[
                StepDefinition(id="step1", step="Setup Flight Declaration", arguments={}),
                StepDefinition(id="error_handler", step="Teardown Flight Declaration", arguments={}, if_condition="failure()"),
            ],
        )

        async def mock_execute_with_context(step, loop_context=None):
            """Mock that adds results to session context."""
            step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
            if session_manager.session_context:
                with session_manager.session_context:
                    session_manager.session_context.add_result(step_result)
            return step_result

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = mock_execute_with_context

            results = await session_manager.run_scenario(scenario)

            # First step executes, second is skipped
            completed = [r for r in results if r.status != Status.RUNNING]
            assert len(completed) == 2
            assert completed[0].status == Status.PASS
            assert completed[1].status == Status.SKIP

    @pytest.mark.asyncio
    async def test_always_condition_runs_regardless(self, session_manager):
        """Test that steps with always() condition always run."""
        scenario = ScenarioDefinition(
            name="Test Conditional",
            description="Test always condition",
            steps=[
                StepDefinition(id="step1", step="Setup Flight Declaration", arguments={}),
                StepDefinition(id="cleanup", step="Teardown Flight Declaration", arguments={}, if_condition="always()"),
            ],
        )

        call_count = 0

        async def mock_execute_with_context(step, loop_context=None):
            """Mock that adds results to session context."""
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                step_result = StepResult(id=step.id, name=step.step, status=Status.FAIL, duration=0.0, result=None)
            else:
                step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
            if session_manager.session_context:
                with session_manager.session_context:
                    session_manager.session_context.add_result(step_result)
            return step_result

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = mock_execute_with_context

            results = await session_manager.run_scenario(scenario)

            # Cleanup should run despite failure
            assert mock_execute.call_count == 2
            assert len([r for r in results if r.status != Status.RUNNING]) == 2

    @pytest.mark.asyncio
    async def test_step_status_condition(self, session_manager):
        """Test condition checking specific step status."""
        scenario = ScenarioDefinition(
            name="Test Conditional",
            description="Test step status check",
            steps=[
                StepDefinition(id="validation", step="Setup Flight Declaration", arguments={}),
                StepDefinition(
                    id="dependent", step="Submit Telemetry", arguments={"duration": 10}, if_condition="steps.validation.status == 'success'"
                ),
            ],
        )

        with patch.object(session_manager, "_execute_step", new_callable=AsyncMock) as mock_execute:

            async def mock_execute_step(step, loop_context=None):
                step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
                if session_manager.session_context:
                    session_manager.session_context.add_result(step_result)
                return step_result

            mock_execute.side_effect = mock_execute_step

            results = await session_manager.run_scenario(scenario)

            # Both should execute since validation succeeds
            assert len([r for r in results if r.status != Status.RUNNING]) == 2
            assert mock_execute.call_count == 2


class TestScenarioWithLoops:
    """Integration tests for scenarios with loops."""

    @pytest.mark.asyncio
    async def test_scenario_with_fixed_count_loop(self, session_manager):
        """Test scenario with fixed count loop."""
        scenario = ScenarioDefinition(
            name="Test Loop Scenario",
            description="Test fixed count loop in scenario",
            steps=[
                StepDefinition(id="retry", step="Setup Flight Declaration", arguments={}, loop=LoopConfig(count=3)),
            ],
        )

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:

            async def mock_execute_step(step, loop_context=None):
                step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
                if session_manager.session_context:
                    with session_manager.session_context:
                        session_manager.session_context.add_result(step_result)
                return step_result

            mock_execute.side_effect = mock_execute_step

            results = await session_manager.run_scenario(scenario)

            # Should execute 3 times
            assert len([r for r in results if r.status != Status.RUNNING]) == 3

    @pytest.mark.asyncio
    async def test_scenario_with_items_loop(self, session_manager):
        """Test scenario with items loop."""
        scenario = ScenarioDefinition(
            name="Test Loop Scenario",
            description="Test items loop in scenario",
            steps=[
                StepDefinition(
                    id="deploy", step="Update Operation State", arguments={"state": "${{ loop.item }}"}, loop=LoopConfig(items=["ACTIVATED", "ENDED"])
                ),
            ],
        )

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:

            async def mock_execute_step(step, loop_context=None):
                step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
                if session_manager.session_context:
                    with session_manager.session_context:
                        session_manager.session_context.add_result(step_result)
                return step_result

            mock_execute.side_effect = mock_execute_step

            results = await session_manager.run_scenario(scenario)

            assert len([r for r in results if r.status != Status.RUNNING]) == 2

    @pytest.mark.asyncio
    async def test_scenario_with_conditional_loop(self, session_manager):
        """Test scenario where loop has a condition."""
        scenario = ScenarioDefinition(
            name="Test Conditional Loop",
            description="Test conditional loop execution",
            steps=[
                StepDefinition(id="setup", step="Setup Flight Declaration", arguments={}),
                StepDefinition(
                    id="conditional_loop", step="Submit Telemetry", arguments={"duration": 5}, if_condition="success()", loop=LoopConfig(count=2)
                ),
            ],
        )

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:

            async def mock_execute_step(step, loop_context=None):
                step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
                if session_manager.session_context:
                    with session_manager.session_context:
                        session_manager.session_context.add_result(step_result)
                return step_result

            mock_execute.side_effect = mock_execute_step

            await session_manager.run_scenario(scenario)

            # Setup + 2 loop iterations = 3 executions
            assert mock_execute.call_count == 3

    @pytest.mark.asyncio
    async def test_accessing_loop_iteration_results(self, session_manager):
        """Test that loop iteration results can be referenced by later steps."""
        scenario = ScenarioDefinition(
            name="Test Loop Results",
            description="Test accessing loop iteration results",
            steps=[
                StepDefinition(id="looped", step="Setup Flight Declaration", arguments={}, loop=LoopConfig(count=2)),
                StepDefinition(
                    id="check_first", step="Submit Telemetry", arguments={"duration": 5}, if_condition="steps.looped[0].status == 'success'"
                ),
            ],
        )

        with patch.object(session_manager, "_execute_step", new_callable=AsyncMock) as mock_execute:

            async def mock_execute_step(step, loop_context=None):
                step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
                if session_manager.session_context:
                    session_manager.session_context.add_result(step_result)
                return step_result

            mock_execute.side_effect = mock_execute_step

            await session_manager.run_scenario(scenario)

            # 2 loop iterations + 1 conditional step
            assert mock_execute.call_count == 3


class TestComplexScenarios:
    """Integration tests for complex scenarios combining multiple features."""

    @pytest.mark.asyncio
    async def test_conditional_with_loop_and_result_check(self, session_manager):
        """Test complex scenario with conditions, loops, and result checks."""
        scenario = ScenarioDefinition(
            name="Complex Test",
            description="Test complex interaction",
            steps=[
                StepDefinition(id="init", step="Setup Flight Declaration", arguments={}),
                StepDefinition(
                    id="batch",
                    step="Submit Telemetry",
                    arguments={"duration": "${{ loop.index }}"},
                    if_condition="success()",
                    loop=LoopConfig(count=3),
                ),
                StepDefinition(
                    id="verify", step="Update Operation State", arguments={"state": "ENDED"}, if_condition="steps.batch[2].status == 'success'"
                ),
                StepDefinition(id="cleanup", step="Teardown Flight Declaration", arguments={}, if_condition="always()"),
            ],
        )

        with patch.object(session_manager, "_execute_step", new_callable=AsyncMock) as mock_execute:

            async def mock_execute_step(step, loop_context=None):
                step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
                if session_manager.session_context:
                    session_manager.session_context.add_result(step_result)
                return step_result

            mock_execute.side_effect = mock_execute_step

            await session_manager.run_scenario(scenario)

            # init + 3 batch iterations + verify + cleanup = 6 executions
            assert mock_execute.call_count == 6

    @pytest.mark.asyncio
    async def test_loop_early_exit_affects_subsequent_conditions(self, session_manager):
        """Test that loop early exit properly affects subsequent condition evaluation."""
        scenario = ScenarioDefinition(
            name="Early Exit Test",
            description="Test loop early exit impact",
            steps=[
                StepDefinition(id="retry", step="Setup Flight Declaration", arguments={}, loop=LoopConfig(count=5)),
                StepDefinition(id="on_complete", step="Submit Telemetry", arguments={"duration": 10}, if_condition="success()"),
            ],
        )

        call_count = 0

        async def mock_with_error(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                step_result = StepResult(
                    id=f"retry[{call_count - 1}]", name="Setup Flight Declaration", status=Status.FAIL, duration=0.0, result=None
                )
            else:
                step_result = StepResult(id="step", name="Setup Flight Declaration", status=Status.PASS, duration=0.0, result=None)
            if session_manager.session_context:
                with session_manager.session_context:
                    session_manager.session_context.add_result(step_result)
            return step_result

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = mock_with_error

            await session_manager.run_scenario(scenario)

            # Loop exits early on iteration 2, subsequent step shouldn't run
            # 2 loop iterations (second fails, breaks scenario)
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_multiple_loops_in_sequence(self, session_manager):
        """Test scenario with multiple sequential loops."""
        scenario = ScenarioDefinition(
            name="Multiple Loops",
            description="Test multiple sequential loops",
            steps=[
                StepDefinition(id="loop1", step="Setup Flight Declaration", arguments={}, loop=LoopConfig(count=2)),
                StepDefinition(id="loop2", step="Submit Telemetry", arguments={"duration": 5}, loop=LoopConfig(count=3)),
            ],
        )

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:

            async def mock_execute_step(step, loop_context=None):
                step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
                if session_manager.session_context:
                    with session_manager.session_context:
                        session_manager.session_context.add_result(step_result)
                return step_result

            mock_execute.side_effect = mock_execute_step

            results = await session_manager.run_scenario(scenario)

            # 2 + 3 = 5 executions
            assert mock_execute.call_count == 5
            assert len([r for r in results if r.status != Status.RUNNING]) == 5


class TestStatusTransitions:
    """Tests for status transitions including WAITING and RUNNING states."""

    @pytest.mark.asyncio
    async def test_waiting_status_for_queued_steps(self, session_manager):
        """Test that steps can be marked as WAITING before execution."""
        scenario = ScenarioDefinition(
            name="Test Waiting Status",
            description="Test WAITING status for queued steps",
            steps=[
                StepDefinition(id="step1", step="Setup Flight Declaration", arguments={}),
                StepDefinition(id="step2", step="Submit Telemetry", arguments={"duration": 10}),
            ],
        )

        recorded_statuses = []

        async def mock_execute_step(step, loop_context=None):
            # Record the step execution
            recorded_statuses.append(("executed", step.id))
            step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
            if session_manager.session_context:
                with session_manager.session_context:
                    session_manager.session_context.add_result(step_result)
            return step_result

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = mock_execute_step

            await session_manager.run_scenario(scenario)

            # Verify steps were executed in order
            assert recorded_statuses == [("executed", "step1"), ("executed", "step2")]

    @pytest.mark.asyncio
    async def test_running_status_for_background_steps(self, session_manager):
        """Test that background steps are marked as RUNNING."""
        scenario = ScenarioDefinition(
            name="Test Running Status",
            description="Test RUNNING status for background steps",
            steps=[
                StepDefinition(id="bg_step", step="Submit Telemetry", arguments={"duration": 30}, background=True),
                StepDefinition(id="foreground", step="Update Operation State", arguments={"state": "ACTIVATED"}),
            ],
        )

        with patch.object(session_manager, "_execute_step", new_callable=AsyncMock) as mock_execute:

            async def mock_execute_step(step, loop_context=None):
                step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
                if session_manager.session_context:
                    session_manager.session_context.add_result(step_result)
                return step_result

            mock_execute.side_effect = mock_execute_step

            await session_manager.run_scenario(scenario)

            # Both steps should have been called
            assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    async def test_status_enum_values(self):
        """Test that all Status enum values are correctly defined."""
        assert Status.PASS == "success"
        assert Status.FAIL == "failure"
        assert Status.RUNNING == "running"
        assert Status.WAITING == "waiting"
        assert Status.SKIP == "skipped"

    @pytest.mark.asyncio
    async def test_step_result_accepts_all_statuses(self):
        """Test that StepResult can be created with all Status values."""
        for status in Status:
            result = StepResult(id="test", name="Test Step", status=status, duration=0.0)
            assert result.status == status

    @pytest.mark.asyncio
    async def test_waiting_to_running_to_pass_transition(self, session_manager):
        """Test the typical status transition: WAITING -> RUNNING -> PASS."""
        scenario = ScenarioDefinition(
            name="Test Status Transition",
            description="Test status transitions",
            steps=[
                StepDefinition(id="step1", step="Setup Flight Declaration", arguments={}),
            ],
        )

        status_transitions = []

        async def mock_execute_with_transitions(step, loop_context=None):
            # Simulate the status transition
            waiting_result = StepResult(id=step.id, name=step.step, status=Status.WAITING, duration=0.0, result=None)
            status_transitions.append(waiting_result.status)

            running_result = StepResult(id=step.id, name=step.step, status=Status.RUNNING, duration=0.0, result=None)
            status_transitions.append(running_result.status)

            final_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
            status_transitions.append(final_result.status)

            if session_manager.session_context:
                with session_manager.session_context:
                    session_manager.session_context.add_result(final_result)
            return final_result

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = mock_execute_with_transitions

            await session_manager.run_scenario(scenario)

            # Verify the transition order
            assert status_transitions == [Status.WAITING, Status.RUNNING, Status.PASS]

    @pytest.mark.asyncio
    async def test_waiting_to_running_to_fail_transition(self, session_manager):
        """Test status transition ending in failure: WAITING -> RUNNING -> FAIL."""
        scenario = ScenarioDefinition(
            name="Test Failure Transition",
            description="Test status transitions ending in failure",
            steps=[
                StepDefinition(id="step1", step="Setup Flight Declaration", arguments={}),
            ],
        )

        status_transitions = []

        async def mock_execute_with_failure(step, loop_context=None):
            status_transitions.append(Status.WAITING)
            status_transitions.append(Status.RUNNING)
            status_transitions.append(Status.FAIL)

            final_result = StepResult(id=step.id, name=step.step, status=Status.FAIL, duration=0.0, result=None, error_message="Simulated failure")
            if session_manager.session_context:
                with session_manager.session_context:
                    session_manager.session_context.add_result(final_result)
            return final_result

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = mock_execute_with_failure

            await session_manager.run_scenario(scenario)

            assert status_transitions == [Status.WAITING, Status.RUNNING, Status.FAIL]

    @pytest.mark.asyncio
    async def test_skip_status_with_condition(self, session_manager):
        """Test that SKIP status is properly assigned when conditions are not met."""
        scenario = ScenarioDefinition(
            name="Test Skip Status",
            description="Test SKIP status assignment",
            steps=[
                StepDefinition(id="step1", step="Setup Flight Declaration", arguments={}),
                StepDefinition(id="step2", step="Submit Telemetry", arguments={"duration": 10}, if_condition="failure()"),
            ],
        )

        async def mock_execute_step(step, loop_context=None):
            step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
            if session_manager.session_context:
                with session_manager.session_context:
                    session_manager.session_context.add_result(step_result)
            return step_result

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = mock_execute_step

            results = await session_manager.run_scenario(scenario)

            # Find step2 result - should be SKIP since failure() is false
            step2_results = [r for r in results if r.id == "step2"]
            assert len(step2_results) == 1
            assert step2_results[0].status == Status.SKIP

    @pytest.mark.asyncio
    async def test_mixed_statuses_in_scenario(self, session_manager):
        """Test scenario with mixed final statuses."""
        scenario = ScenarioDefinition(
            name="Test Mixed Statuses",
            description="Test scenario with various statuses",
            steps=[
                StepDefinition(id="pass_step", step="Setup Flight Declaration", arguments={}),
                StepDefinition(id="fail_step", step="Submit Telemetry", arguments={"duration": 10}),
                StepDefinition(id="conditional_step", step="Update Operation State", arguments={"state": "ENDED"}, if_condition="failure()"),
                StepDefinition(id="always_step", step="Teardown Flight Declaration", arguments={}, if_condition="always()"),
            ],
        )

        call_count = 0

        async def mock_execute_with_mixed_results(step, loop_context=None):
            nonlocal call_count
            call_count += 1

            if step.id == "fail_step":
                status = Status.FAIL
            else:
                status = Status.PASS

            step_result = StepResult(id=step.id, name=step.step, status=status, duration=0.0, result=None)
            if session_manager.session_context:
                with session_manager.session_context:
                    session_manager.session_context.add_result(step_result)
            return step_result

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = mock_execute_with_mixed_results

            results = await session_manager.run_scenario(scenario)

            # Verify we have various statuses
            status_map = {r.id: r.status for r in results if r.id}
            assert status_map.get("pass_step") == Status.PASS
            assert status_map.get("fail_step") == Status.FAIL
            # conditional_step runs because failure() is true after fail_step
            assert status_map.get("conditional_step") == Status.PASS
            assert status_map.get("always_step") == Status.PASS  # Always runs


class TestConditionEvaluatorWithStatuses:
    """Tests for condition evaluation with various status values."""

    def test_success_condition_with_waiting_status(self):
        """Test that success() returns False when last status is WAITING."""
        from openutm_verification.core.execution.conditions import ConditionEvaluator

        steps = {"step1": StepResult(id="step1", name="Test", status=Status.WAITING, duration=0.0)}
        evaluator = ConditionEvaluator(steps)

        # WAITING is not considered success
        assert evaluator.evaluate("success()") is False

    def test_success_condition_with_running_status(self):
        """Test that success() returns True when last status is RUNNING."""
        from openutm_verification.core.execution.conditions import ConditionEvaluator

        steps = {"step1": StepResult(id="step1", name="Test", status=Status.RUNNING, duration=0.0)}
        evaluator = ConditionEvaluator(steps)

        # RUNNING is considered success (allows downstream steps to start)
        assert evaluator.evaluate("success()") is True

    def test_failure_condition_with_waiting_status(self):
        """Test that failure() returns False when last status is WAITING."""
        from openutm_verification.core.execution.conditions import ConditionEvaluator

        steps = {"step1": StepResult(id="step1", name="Test", status=Status.WAITING, duration=0.0)}
        evaluator = ConditionEvaluator(steps)

        # WAITING is not considered failure
        assert evaluator.evaluate("failure()") is False

    def test_failure_condition_with_skip_status(self):
        """Test that failure() returns False when last status is SKIP."""
        from openutm_verification.core.execution.conditions import ConditionEvaluator

        steps = {"step1": StepResult(id="step1", name="Test", status=Status.SKIP, duration=0.0)}
        evaluator = ConditionEvaluator(steps)

        # SKIP is not considered failure
        assert evaluator.evaluate("failure()") is False

    def test_step_status_comparison_with_waiting(self):
        """Test direct status comparison with WAITING."""
        from openutm_verification.core.execution.conditions import ConditionEvaluator

        steps = {"step1": StepResult(id="step1", name="Test", status=Status.WAITING, duration=0.0)}
        evaluator = ConditionEvaluator(steps)

        assert evaluator.evaluate("steps.step1.status == 'waiting'") is True
        assert evaluator.evaluate("steps.step1.status == 'success'") is False

    def test_step_status_comparison_with_running(self):
        """Test direct status comparison with RUNNING."""
        from openutm_verification.core.execution.conditions import ConditionEvaluator

        steps = {"step1": StepResult(id="step1", name="Test", status=Status.RUNNING, duration=0.0)}
        evaluator = ConditionEvaluator(steps)

        assert evaluator.evaluate("steps.step1.status == 'running'") is True
        assert evaluator.evaluate("steps.step1.status == 'success'") is False

    def test_last_step_excludes_skipped(self):
        """Test that last_step_status excludes skipped steps."""
        from openutm_verification.core.execution.conditions import ConditionEvaluator

        # Skipped steps should not affect the "last step" status
        steps = {
            "step1": StepResult(id="step1", name="Test1", status=Status.PASS, duration=0.0),
            "step2": StepResult(id="step2", name="Test2", status=Status.SKIP, duration=0.0),
        }
        evaluator = ConditionEvaluator(steps)

        # success() should check step1 (PASS), not step2 (SKIP)
        assert evaluator.evaluate("success()") is True
