"""Tests for loop execution in the runner."""

from unittest.mock import AsyncMock, patch

import pytest

from openutm_verification.core.execution.definitions import LoopConfig, ScenarioDefinition, StepDefinition
from openutm_verification.core.reporting.reporting_models import Status, StepResult
from openutm_verification.server.runner import SessionManager


@pytest.fixture
def session_manager():
    """Create a SessionManager instance for testing."""
    manager = SessionManager()
    manager.session_resolver = None
    manager.session_context = None
    manager.session_stack = None
    if manager.session_context and manager.session_context.state:
        manager.session_context.state.steps.clear()
    return manager


class TestLoopExecution:
    """Test loop execution functionality."""

    @pytest.mark.asyncio
    async def test_fixed_count_loop(self, session_manager):
        """Test loop with fixed count."""
        scenario = ScenarioDefinition(
            name="Test Loop",
            description="Test fixed count loop",
            steps=[StepDefinition(id="test_loop", step="Setup Flight Declaration", arguments={}, loop=LoopConfig(count=3))],
        )

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = StepResult(id="test_loop[0]", name="Setup Flight Declaration", status=Status.PASS, duration=0.0, result=None)

            results = await session_manager._execute_loop(scenario.steps[0])

            assert len(results) == 3
            assert mock_execute.call_count == 3

            # Verify loop context was passed
            for i, call in enumerate(mock_execute.call_args_list):
                loop_context = call[0][1]  # Second argument
                assert loop_context["index"] == i
                assert loop_context["item"] == i

    @pytest.mark.asyncio
    async def test_items_loop(self, session_manager):
        """Test loop with items."""
        items = ["ACTIVATED", "CONTINGENT", "ENDED"]
        scenario = ScenarioDefinition(
            name="Test Loop",
            description="Test items loop",
            steps=[
                StepDefinition(id="test_loop", step="Update Operation State", arguments={"state": "${{ loop.item }}"}, loop=LoopConfig(items=items))
            ],
        )

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = StepResult(id="test_loop[0]", name="Update Operation State", status=Status.PASS, duration=0.0, result=None)

            results = await session_manager._execute_loop(scenario.steps[0])

            assert len(results) == 3

            # Verify loop context contains correct items
            for i, call in enumerate(mock_execute.call_args_list):
                loop_context = call[0][1]
                assert loop_context["index"] == i
                assert loop_context["item"] == items[i]

    @pytest.mark.asyncio
    async def test_while_loop_with_limit(self, session_manager):
        """Test while loop with condition."""
        scenario = ScenarioDefinition(
            name="Test Loop",
            description="Test while loop",
            steps=[StepDefinition(id="test_loop", step="Setup Flight Declaration", arguments={}, loop=LoopConfig(while_condition="loop.index < 3"))],
        )

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = StepResult(id="test_loop[0]", name="Setup Flight Declaration", status=Status.PASS, duration=0.0, result=None)

            results = await session_manager._execute_loop(scenario.steps[0])

            # Should execute while index < 3 (0, 1, 2)
            assert len(results) == 3
            assert mock_execute.call_count == 3

    @pytest.mark.asyncio
    async def test_loop_with_early_termination(self, session_manager):
        """Test loop that terminates early on error."""
        scenario = ScenarioDefinition(
            name="Test Loop",
            description="Test loop early termination",
            steps=[StepDefinition(id="test_loop", step="Setup Flight Declaration", arguments={}, loop=LoopConfig(count=5))],
        )

        call_count = 0

        async def mock_execute_with_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return StepResult(id=f"test_loop[{call_count - 1}]", name="Setup Flight Declaration", status=Status.FAIL, duration=0.0, result=None)
            return StepResult(id=f"test_loop[{call_count - 1}]", name="Setup Flight Declaration", status=Status.PASS, duration=0.0, result=None)

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = mock_execute_with_failure

            results = await session_manager._execute_loop(scenario.steps[0])

            # Should stop after error on iteration 2
            assert len(results) == 2
            assert results[0].status == Status.PASS
            assert results[1].status == Status.FAIL

    @pytest.mark.asyncio
    async def test_combined_count_and_while(self, session_manager):
        """Test loop with both count and while condition."""
        scenario = ScenarioDefinition(
            name="Test Loop",
            description="Test combined loop",
            steps=[
                StepDefinition(
                    id="test_loop", step="Setup Flight Declaration", arguments={}, loop=LoopConfig(count=10, while_condition="loop.index < 3")
                )
            ],
        )

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = StepResult(id="test_loop[0]", name="Setup Flight Declaration", status=Status.PASS, duration=0.0, result=None)

            results = await session_manager._execute_loop(scenario.steps[0])

            # Should stop at 3 due to while condition, not reach 10
            assert len(results) == 3

    @pytest.mark.asyncio
    async def test_loop_creates_indexed_step_ids(self, session_manager):
        """Test that loop iterations create proper step IDs."""
        scenario = ScenarioDefinition(
            name="Test Loop",
            description="Test step ID generation",
            steps=[StepDefinition(id="my_loop", step="Setup Flight Declaration", arguments={}, loop=LoopConfig(count=2))],
        )

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = StepResult(id="my_loop[0]", name="Setup Flight Declaration", status=Status.PASS, duration=0.0, result=None)

            await session_manager._execute_loop(scenario.steps[0])

            # Check that step IDs were modified with index
            for i, call in enumerate(mock_execute.call_args_list):
                step = call[0][0]  # First argument is the step
                assert step.id == f"my_loop[{i}]"

    @pytest.mark.asyncio
    async def test_while_loop_max_iterations(self, session_manager):
        """Test while loop respects max iteration limit."""
        scenario = ScenarioDefinition(
            name="Test Loop",
            description="Test max iterations",
            steps=[
                StepDefinition(
                    id="infinite_loop",
                    step="Setup Flight Declaration",
                    arguments={},
                    loop=LoopConfig(while_condition="loop.index < 200"),  # Would exceed max
                )
            ],
        )

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = StepResult(
                id="infinite_loop[0]", name="Setup Flight Declaration", status=Status.PASS, duration=0.0, result=None
            )

            results = await session_manager._execute_loop(scenario.steps[0])

            # Should stop at max iterations (100)
            assert len(results) == 100

    @pytest.mark.asyncio
    async def test_loop_variable_replacement_in_arguments(self, session_manager):
        """Test that loop variables are properly resolved in arguments."""
        # Initialize session to ensure resolver exists
        await session_manager.initialize_session()

        items = ["item1", "item2", "item3"]
        step = StepDefinition(
            id="test", step="Some Action", arguments={"value": "${{ loop.item }}", "index": "${{ loop.index }}"}, loop=LoopConfig(items=items)
        )

        loop_context = {"index": 1, "item": "item2"}

        # Test _prepare_params with loop context
        params = session_manager._prepare_params(step, loop_context)

        assert params["value"] == "item2"
        assert params["index"] == 1

    @pytest.mark.asyncio
    async def test_nested_loop_items(self, session_manager):
        """Test loop with complex nested items."""
        items = [{"name": "dev", "url": "dev.example.com"}, {"name": "prod", "url": "prod.example.com"}]

        scenario = ScenarioDefinition(
            name="Test Loop",
            description="Test nested items",
            steps=[
                StepDefinition(
                    id="test_loop", step="Setup Flight Declaration", arguments={"config": "${{ loop.item }}"}, loop=LoopConfig(items=items)
                )
            ],
        )

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = StepResult(id="test_loop[0]", name="Update Operation State", status=Status.PASS, duration=0.0, result=None)

            results = await session_manager._execute_loop(scenario.steps[0])

            assert len(results) == 2

            # Verify complex items are passed correctly
            for i, call in enumerate(mock_execute.call_args_list):
                loop_context = call[0][1]
                assert loop_context["item"] == items[i]

    @pytest.mark.asyncio
    async def test_empty_items_list(self, session_manager):
        """Test loop with empty items list."""
        scenario = ScenarioDefinition(
            name="Test Loop",
            description="Test empty items",
            steps=[StepDefinition(id="test_loop", step="Setup Flight Declaration", arguments={}, loop=LoopConfig(items=[]))],
        )

        with patch.object(session_manager, "execute_single_step", new_callable=AsyncMock) as mock_execute:
            results = await session_manager._execute_loop(scenario.steps[0])

            # Should not execute anything
            assert len(results) == 0
            assert mock_execute.call_count == 0


class TestLoopWithConditions:
    """Test interaction between loops and conditions."""

    @pytest.mark.asyncio
    async def test_conditional_loop_execution(self, session_manager):
        """Test loop that only runs if condition is met."""
        # This would be tested in the run_scenario method
        # where if conditions are evaluated before loops
        pass

    @pytest.mark.asyncio
    async def test_loop_with_step_reference_in_while(self, session_manager):
        """Test while condition referencing previous step results."""
        # This requires full scenario context with step results
        pass
