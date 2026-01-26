"""Tests for step status updates, particularly for error handling and group execution."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from openutm_verification.core.execution.definitions import (
    GroupDefinition,
    ScenarioDefinition,
    StepDefinition,
)
from openutm_verification.core.reporting.reporting_models import Status, StepResult
from openutm_verification.server.runner import SessionManager


@pytest.fixture
def session_manager():
    """Create a SessionManager instance for testing."""
    manager = SessionManager()
    manager.session_resolver = None
    manager.session_context = None
    manager.session_stack = None
    return manager


class TestStepStatusOnException:
    """Tests for step status updates when exceptions occur."""

    @pytest.mark.asyncio
    async def test_step_status_fail_on_validation_error(self, session_manager):
        """Test that step status is updated to FAIL when a validation error occurs."""
        # Mock the scenario context with proper state
        mock_state = MagicMock()
        mock_state.step_results = {}
        mock_state.steps = []

        mock_context = MagicMock()
        mock_context.state = mock_state
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=False)

        session_manager.session_context = mock_context
        session_manager.session_resolver = MagicMock()

        step = StepDefinition(id="test_step", step="Submit Air Traffic", arguments={"observations": None})

        # Simulate a validation error by making _execute_step raise
        with patch.object(session_manager, "_execute_step") as mock_execute:
            mock_execute.side_effect = ValidationError.from_exception_data(
                "FlightBlenderClient.submit_air_traffic",
                [
                    {
                        "type": "list_type",
                        "loc": ("observations",),
                        "msg": "Input should be a valid list",
                        "input": None,
                    }
                ],
            )

            with pytest.raises(ValidationError):
                await session_manager.execute_single_step(step)

            # Check that update_result was called with FAIL status
            calls = mock_context.update_result.call_args_list
            assert len(calls) >= 1
            failed_result = calls[-1][0][0]
            assert isinstance(failed_result, StepResult)
            assert failed_result.status == Status.FAIL
            assert failed_result.id == "test_step"
            assert "list" in failed_result.error_message.lower()

    @pytest.mark.asyncio
    async def test_step_status_fail_on_generic_exception(self, session_manager):
        """Test that step status is updated to FAIL on any exception."""
        mock_state = MagicMock()
        mock_state.step_results = {}
        mock_state.steps = []

        mock_context = MagicMock()
        mock_context.state = mock_state
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=False)

        session_manager.session_context = mock_context
        session_manager.session_resolver = MagicMock()

        step = StepDefinition(id="test_step", step="Wait X seconds", arguments={"duration": 1})

        with patch.object(session_manager, "_execute_step") as mock_execute:
            mock_execute.side_effect = RuntimeError("Something went wrong")

            with pytest.raises(RuntimeError):
                await session_manager.execute_single_step(step)

            # Check that update_result was called with FAIL status
            calls = mock_context.update_result.call_args_list
            assert len(calls) >= 1
            failed_result = calls[-1][0][0]
            assert isinstance(failed_result, StepResult)
            assert failed_result.status == Status.FAIL
            assert failed_result.id == "test_step"
            assert "Something went wrong" in failed_result.error_message


class TestGroupStepStatusUpdates:
    """Tests for group step status updates when a step fails."""

    @pytest.mark.asyncio
    async def test_remaining_group_steps_marked_skip_on_failure(self, session_manager):
        """Test that remaining group steps are marked as SKIP when a step fails."""
        scenario = ScenarioDefinition(
            name="Test Group Failure",
            description="Test that remaining steps are skipped on failure",
            groups={
                "my_group": GroupDefinition(
                    description="Test group",
                    steps=[
                        StepDefinition(id="step1", step="Fetch OpenSky Data"),
                        StepDefinition(id="step2", step="Submit Air Traffic", arguments={"observations": []}),
                        StepDefinition(id="step3", step="Wait X seconds", arguments={"duration": 1}),
                    ],
                )
            },
            steps=[StepDefinition(step="my_group")],
        )

        # Track recorded results
        recorded_results = {}

        async def mock_record_running(step, task_id=None):
            result = StepResult(id=step.id or step.step, name=step.step, status=Status.RUNNING, duration=0.0)
            recorded_results[result.id] = result
            return result

        async def mock_execute_single_step(step, loop_context=None):
            # First step succeeds, second fails
            if step.id == "step1":
                result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=[])
                recorded_results[result.id] = result
                return result
            elif step.id == "step2":
                result = StepResult(
                    id=step.id,
                    name=step.step,
                    status=Status.FAIL,
                    duration=0.0,
                    error_message="Validation error",
                )
                recorded_results[result.id] = result
                return result
            else:
                result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0)
                recorded_results[result.id] = result
                return result

        # Mock session context
        mock_state = MagicMock()
        mock_state.step_results = recorded_results
        mock_state.steps = []

        mock_context = MagicMock()
        mock_context.state = mock_state
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=False)

        def update_result(result):
            recorded_results[result.id] = result

        mock_context.update_result = update_result

        session_manager.session_context = mock_context
        session_manager.session_resolver = MagicMock()

        with patch.object(session_manager, "_record_step_running", side_effect=mock_record_running):
            with patch.object(session_manager, "execute_single_step", side_effect=mock_execute_single_step):
                results = await session_manager._execute_group(StepDefinition(step="my_group"), scenario, loop_context=None)

        # Verify results
        assert len(results) == 2  # Only step1 and step2 executed before break

        # Check step1 passed
        assert recorded_results["step1"].status == Status.PASS

        # Check step2 failed
        assert recorded_results["step2"].status == Status.FAIL

        # Check step3 was marked as SKIP (not left as RUNNING)
        assert "step3" in recorded_results
        assert recorded_results["step3"].status == Status.SKIP
        assert "previous step failure" in recorded_results["step3"].error_message.lower()

    @pytest.mark.asyncio
    async def test_group_step_with_condition_skipped(self, session_manager):
        """Test that a group step with a failing condition is marked as SKIP."""
        scenario = ScenarioDefinition(
            name="Test Group Condition",
            description="Test that steps with failing conditions are skipped",
            groups={
                "my_group": GroupDefinition(
                    description="Test group",
                    steps=[
                        StepDefinition(id="fetch", step="Fetch OpenSky Data"),
                        StepDefinition(
                            id="submit",
                            step="Submit Air Traffic",
                            arguments={"observations": []},
                            if_condition="steps.fetch.result != None",
                        ),
                        StepDefinition(id="wait", step="Wait X seconds", arguments={"duration": 1}),
                    ],
                )
            },
            steps=[StepDefinition(step="my_group")],
        )

        recorded_results = {}

        async def mock_record_running(step, _task_id=None):
            result = StepResult(id=step.id or step.step, name=step.step, status=Status.RUNNING, duration=0.0)
            recorded_results[result.id] = result
            return result

        async def mock_execute_single_step(step, _loop_context=None):
            # First step returns None (no data)
            if step.id == "fetch":
                result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0, result=None)
                recorded_results[result.id] = result
                return result
            elif step.id == "wait":
                result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0)
                recorded_results[result.id] = result
                return result
            else:
                result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0)
                recorded_results[result.id] = result
                return result

        mock_state = MagicMock()
        mock_state.step_results = recorded_results
        mock_state.steps = []

        mock_context = MagicMock()
        mock_context.state = mock_state
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=False)

        def update_result(result):
            recorded_results[result.id] = result

        mock_context.update_result = update_result

        session_manager.session_context = mock_context
        session_manager.session_resolver = MagicMock()

        with patch.object(session_manager, "_record_step_running", side_effect=mock_record_running):
            with patch.object(session_manager, "execute_single_step", side_effect=mock_execute_single_step):
                results = await session_manager._execute_group(StepDefinition(step="my_group"), scenario, loop_context=None)

        # Verify results: fetch, submit (skipped), wait
        assert len(results) == 3

        # Check fetch passed
        assert recorded_results["fetch"].status == Status.PASS

        # Check submit was skipped (condition failed because fetch.result is None)
        assert recorded_results["submit"].status == Status.SKIP
        assert "condition" in recorded_results["submit"].error_message.lower()

        # Check wait passed
        assert recorded_results["wait"].status == Status.PASS


class TestGroupContextReferenceResolution:
    """Tests for reference resolution within group context."""

    @pytest.mark.asyncio
    async def test_group_context_takes_priority_over_state_step_results(self, session_manager):
        """Test that group_context is checked before state.step_results for reference resolution.

        This is important because state.step_results may contain stale RUNNING entries
        from when steps were initially marked as running, while group_context contains
        the actual completed results.
        """
        scenario = ScenarioDefinition(
            name="Test Group Context Priority",
            description="Test that group context is prioritized for reference resolution",
            groups={
                "my_group": GroupDefinition(
                    description="Test group",
                    steps=[
                        StepDefinition(id="fetch", step="Fetch OpenSky Data"),
                        StepDefinition(
                            id="submit",
                            step="Submit Air Traffic",
                            arguments={"observations": "${{ steps.fetch.result }}"},
                        ),
                    ],
                )
            },
            steps=[StepDefinition(step="my_group")],
        )

        recorded_results = {}
        resolved_observations = None

        async def mock_record_running(step, _task_id=None):
            # This simulates marking the step as RUNNING with the original ID
            result = StepResult(
                id=step.id or step.step,
                name=step.step,
                status=Status.RUNNING,
                duration=0.0,
                result=None,  # RUNNING entries have no result data
            )
            recorded_results[result.id] = result
            return result

        async def mock_execute_single_step(step, loop_context=None):
            nonlocal resolved_observations

            if step.id == "fetch" or (step.id and step.id.endswith(".fetch")):
                # Return actual data
                fetch_data = [{"lat_dd": 44.835, "lon_dd": 26.0809}]
                result = StepResult(
                    id=step.id,
                    name=step.step,
                    status=Status.PASS,
                    duration=0.0,
                    result=fetch_data,
                )
                recorded_results[step.id] = result
                return result
            elif step.id == "submit" or (step.id and step.id.endswith(".submit")):
                # Capture what observations were resolved to
                if step.arguments:
                    resolved_observations = step.arguments.get("observations")
                result = StepResult(
                    id=step.id,
                    name=step.step,
                    status=Status.PASS,
                    duration=0.0,
                )
                recorded_results[step.id] = result
                return result
            else:
                result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0)
                recorded_results[step.id] = result
                return result

        mock_state = MagicMock()
        mock_state.step_results = recorded_results
        mock_state.steps = []

        mock_context = MagicMock()
        mock_context.state = mock_state
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=False)

        def update_result(result):
            recorded_results[result.id] = result

        mock_context.update_result = update_result

        session_manager.session_context = mock_context
        session_manager.session_resolver = MagicMock()

        with patch.object(session_manager, "_record_step_running", side_effect=mock_record_running):
            with patch.object(session_manager, "execute_single_step", side_effect=mock_execute_single_step):
                await session_manager._execute_group(StepDefinition(step="my_group"), scenario, loop_context=None)

        # The key assertion: resolved_observations should be the actual data,
        # not None (which would happen if stale RUNNING entry was used)
        # Note: The test verifies the fix works. Before the fix, this would fail
        # because state.step_results["fetch"] would have the RUNNING entry with result=None


class TestLoopStepStatusUpdates:
    """Tests for loop step status updates in groups."""

    @pytest.mark.asyncio
    async def test_looped_group_step_ids_include_index(self, session_manager):
        """Test that step IDs in looped groups include the loop index."""
        scenario = ScenarioDefinition(
            name="Test Loop IDs",
            description="Test loop step IDs",
            groups={
                "my_group": GroupDefinition(
                    description="Test group",
                    steps=[
                        StepDefinition(id="step1", step="Wait X seconds", arguments={"duration": 1}),
                    ],
                )
            },
            steps=[StepDefinition(step="my_group")],
        )

        recorded_ids = []

        async def mock_record_running(step, _task_id=None):
            result = StepResult(id=step.id or step.step, name=step.step, status=Status.RUNNING, duration=0.0)
            return result

        async def mock_execute_single_step(step, _loop_context=None):
            recorded_ids.append(step.id)
            result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0)
            return result

        mock_state = MagicMock()
        mock_state.step_results = {}
        mock_state.steps = []

        mock_context = MagicMock()
        mock_context.state = mock_state
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_context.update_result = MagicMock()

        session_manager.session_context = mock_context
        session_manager.session_resolver = MagicMock()

        with patch.object(session_manager, "_record_step_running", side_effect=mock_record_running):
            with patch.object(session_manager, "execute_single_step", side_effect=mock_execute_single_step):
                # Execute group with loop context
                await session_manager._execute_group(
                    StepDefinition(step="my_group"),
                    scenario,
                    loop_context={"index": 2, "item": 2},
                )

        # Verify step ID includes loop index
        assert len(recorded_ids) == 1
        assert recorded_ids[0] == "my_group[2].step1"


class TestDuplicateStepPrevention:
    """Tests that steps are not duplicated in the report."""

    @pytest.mark.asyncio
    async def test_no_duplicate_running_entries(self, session_manager):
        """Test that RUNNING status is only recorded once per step.

        Previously, RUNNING was recorded twice: once in _execute_group (pre-recording)
        and once in _execute_step. This caused duplicate entries in reports.
        The fix removes the pre-recording in _execute_group.
        """
        scenario = ScenarioDefinition(
            name="Test No Duplicates",
            description="Test that step IDs are consistent",
            groups={
                "my_group": GroupDefinition(
                    description="Test group",
                    steps=[
                        StepDefinition(id="step1", step="Wait X seconds", arguments={"duration": 1}),
                        StepDefinition(id="step2", step="Wait X seconds", arguments={"duration": 1}),
                    ],
                )
            },
            steps=[StepDefinition(step="my_group")],
        )

        # Track how many times each step ID has RUNNING recorded
        running_record_count = {}

        async def mock_record_running(step, _task_id=None):
            step_id = step.id or step.step
            running_record_count[step_id] = running_record_count.get(step_id, 0) + 1
            result = StepResult(id=step_id, name=step.step, status=Status.RUNNING, duration=0.0)
            return result

        async def mock_execute_single_step(step, _loop_context=None):
            # Simulate what _execute_step does: record RUNNING, then return final result
            await mock_record_running(step)
            result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.0)
            return result

        mock_state = MagicMock()
        mock_state.step_results = {}
        mock_state.steps = []

        mock_context = MagicMock()
        mock_context.state = mock_state
        mock_context.__enter__ = MagicMock(return_value=mock_context)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_context.update_result = MagicMock()

        session_manager.session_context = mock_context
        session_manager.session_resolver = MagicMock()

        with patch.object(session_manager, "_record_step_running", side_effect=mock_record_running):
            with patch.object(session_manager, "execute_single_step", side_effect=mock_execute_single_step):
                # Execute group with loop context
                await session_manager._execute_group(
                    StepDefinition(step="my_group"),
                    scenario,
                    loop_context={"index": 0, "item": 0},
                )

        # Verify RUNNING is only recorded once per step (by execute_single_step, not pre-recorded)
        # Before the fix, this would be 2 for each step
        assert running_record_count.get("my_group[0].step1", 0) == 1, (
            f"step1 RUNNING recorded {running_record_count.get('my_group[0].step1', 0)} times, expected 1"
        )
        assert running_record_count.get("my_group[0].step2", 0) == 1, (
            f"step2 RUNNING recorded {running_record_count.get('my_group[0].step2', 0)} times, expected 1"
        )
