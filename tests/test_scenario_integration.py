"""Integration tests for conditional execution and loops in scenarios."""

from unittest.mock import AsyncMock, patch

import pytest

from openutm_verification.core.execution.definitions import LoopConfig, ScenarioDefinition, StepDefinition
from openutm_verification.core.reporting.reporting_models import Status, StepResult
from openutm_verification.server.runner import SessionManager


@pytest.fixture
def session_manager():
    """Create a SessionManager instance for testing."""
    return SessionManager()


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
            mock_execute.return_value = {"id": "step1", "status": "success", "result": None}

            results = await session_manager.run_scenario(scenario)

            # Both steps should execute
            assert len(results) == 2
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
            from openutm_verification.core.reporting.reporting_models import Status, StepResult

            result = {"id": step.id, "status": "success", "result": None}
            # Add result to session context
            step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
            session_manager.session_context.add_result(step_result)
            return result

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = mock_execute_with_context

            results = await session_manager.run_scenario(scenario)

            # First step executes, second is skipped
            assert len(results) == 2
            assert results[0]["status"] == "success"
            assert results[1]["status"] == "skipped"

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
            from openutm_verification.core.reporting.reporting_models import Status, StepResult

            if call_count == 1:
                # First step fails
                result = {"id": step.id, "status": "error", "result": None}
                step_result = StepResult(id=step.id, name=step.step, status=Status.FAIL, duration=0.0, result=None)
            else:
                # Cleanup succeeds
                result = {"id": step.id, "status": "success", "result": None}
                step_result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)

            session_manager.session_context.add_result(step_result)
            return result

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = mock_execute_with_context

            results = await session_manager.run_scenario(scenario)

            # Cleanup should run despite failure
            assert mock_execute.call_count == 2
            assert len(results) == 2

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
                result = {"id": step.id, "status": "success", "result": None}
                # Add to session context properly
                if session_manager.session_context and session_manager.session_context.state:
                    session_manager.session_context.add_result(StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None))
                return result

            mock_execute.side_effect = mock_execute_step

            results = await session_manager.run_scenario(scenario)

            # Both should execute since validation succeeds
            assert len(results) == 2
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
            mock_execute.return_value = {"id": "retry[0]", "status": "success", "result": None}

            results = await session_manager.run_scenario(scenario)

            # Should execute 3 times
            assert len(results) == 3

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
            mock_execute.return_value = {"id": "deploy[0]", "status": "success", "result": None}

            results = await session_manager.run_scenario(scenario)

            assert len(results) == 2

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
            mock_execute.return_value = {"id": "step", "status": "success", "result": None}

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
                result = {"id": step.id, "status": "success", "result": None}
                # Add to session context properly with the actual step ID
                if session_manager.session_context and session_manager.session_context.state:
                    session_manager.session_context.add_result(StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None))
                return result

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
                result = {"id": step.id, "status": "success", "result": None}
                # Add to session context properly with the actual step ID
                if session_manager.session_context and session_manager.session_context.state:
                    session_manager.session_context.add_result(StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None))
                return result

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
                return {"id": f"retry[{call_count - 1}]", "status": "error", "result": None}
            return {"id": "step", "status": "success", "result": None}

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
            mock_execute.return_value = {"id": "step", "status": "success", "result": None}

            results = await session_manager.run_scenario(scenario)

            # 2 + 3 = 5 executions
            assert mock_execute.call_count == 5
            assert len(results) == 5
