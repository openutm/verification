"""Integration tests for continue-on-error runner behavior.

Validates that the SessionManager.run_scenario properly continues
execution after failures when continue-on-error is set, and that
the failed StepResult is marked continue_on_error=True.
"""

from unittest.mock import AsyncMock, patch

import pytest

from openutm_verification.core.execution.definitions import (
    GroupDefinition,
    ScenarioDefinition,
    StepDefinition,
)
from openutm_verification.core.execution.scenario_runner import ScenarioContext
from openutm_verification.core.reporting.reporting_models import Status, StepResult
from openutm_verification.server.runner import SessionManager


def _make_runner() -> SessionManager:
    """Create a minimal SessionManager with mocked internals."""
    SessionManager._instance = None
    runner = SessionManager.__new__(SessionManager)
    runner._initialized = True
    runner.config_path = None
    runner.config = type(
        "C",
        (),
        {
            "suites": {},
            "reporting": type("R", (), {"output_dir": "/tmp/reports", "formats": []})(),
        },
    )()
    runner.client_map = {}
    runner.session_stack = None
    runner.session_resolver = None
    runner.session_context = None
    runner.session_tasks = {}
    runner.current_start_time = None
    runner.current_output_dir = None
    runner.current_timestamp_str = None
    runner.current_run_error = None
    runner.data_files = None
    runner._stop_event = None
    return runner


def _setup_session(runner: SessionManager) -> None:
    """Prepare a fresh ScenarioContext on the runner."""
    ctx = ScenarioContext()
    ctx.__enter__()
    runner.session_context = ctx


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Ensure SessionManager singleton is reset between tests."""
    SessionManager._instance = None
    yield
    SessionManager._instance = None


# ── Regular step tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_continue_on_error_continues_after_failure():
    """Scenario continues executing steps after a continue-on-error failure."""
    runner = _make_runner()
    _setup_session(runner)

    scenario = ScenarioDefinition(
        name="test",
        steps=[
            StepDefinition(step="step_a", id="step_a", **{"continue-on-error": True}),
            StepDefinition(step="step_b", id="step_b"),
        ],
    )

    call_order = []

    async def fake_execute(step, loop_context=None):
        call_order.append(step.id)
        if step.id == "step_a":
            result = StepResult(id=step.id, name=step.step, status=Status.FAIL, duration=0.1, error_message="boom")
        else:
            result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.1)
        with runner.session_context:
            runner.session_context.update_result(result)
        return result

    with patch.object(runner, "execute_single_step", side_effect=fake_execute):
        with patch.object(runner, "initialize_session", new_callable=AsyncMock):
            with patch.object(runner, "_wait_for_dependencies", new_callable=AsyncMock):
                results = await runner.run_scenario(scenario)

    assert call_order == ["step_a", "step_b"], "step_b should have executed after step_a failed with continue-on-error"

    step_a_result = next(r for r in results if r.id == "step_a")
    assert step_a_result.status == Status.FAIL
    assert step_a_result.continue_on_error is True

    step_b_result = next(r for r in results if r.id == "step_b")
    assert step_b_result.status == Status.PASS


@pytest.mark.asyncio
async def test_without_continue_on_error_stops_after_failure():
    """Scenario stops executing steps after a failure without continue-on-error."""
    runner = _make_runner()
    _setup_session(runner)

    scenario = ScenarioDefinition(
        name="test",
        steps=[
            StepDefinition(step="step_a", id="step_a"),
            StepDefinition(step="step_b", id="step_b"),
        ],
    )

    call_order = []

    async def fake_execute(step, loop_context=None):
        call_order.append(step.id)
        if step.id == "step_a":
            result = StepResult(id=step.id, name=step.step, status=Status.FAIL, duration=0.1, error_message="boom")
        else:
            result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.1)
        with runner.session_context:
            runner.session_context.update_result(result)
        return result

    with patch.object(runner, "execute_single_step", side_effect=fake_execute):
        with patch.object(runner, "initialize_session", new_callable=AsyncMock):
            with patch.object(runner, "_wait_for_dependencies", new_callable=AsyncMock):
                await runner.run_scenario(scenario)

    assert call_order == ["step_a"], "step_b should NOT have executed"


# ── Group step tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_continue_on_error_inside_group():
    """A group step with continue-on-error allows subsequent group steps to run."""
    runner = _make_runner()
    _setup_session(runner)

    scenario = ScenarioDefinition(
        name="test",
        groups={
            "my_group": GroupDefinition(
                steps=[
                    StepDefinition(step="g_step1", id="g_step1", **{"continue-on-error": True}),
                    StepDefinition(step="g_step2", id="g_step2"),
                ],
            ),
        },
        steps=[
            StepDefinition(step="my_group", id="run_group"),
        ],
    )

    call_order = []

    async def fake_execute(step, loop_context=None):
        call_order.append(step.id)
        if step.step == "g_step1":
            result = StepResult(id=step.id, name=step.step, status=Status.FAIL, duration=0.1, error_message="boom")
        else:
            result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.1)
        with runner.session_context:
            runner.session_context.update_result(result)
        return result

    with patch.object(runner, "execute_single_step", side_effect=fake_execute):
        with patch.object(runner, "initialize_session", new_callable=AsyncMock):
            with patch.object(runner, "_wait_for_dependencies", new_callable=AsyncMock):
                results = await runner.run_scenario(scenario)

    assert "g_step1" in call_order
    assert "g_step2" in call_order, "g_step2 should execute because g_step1 has continue-on-error"

    g1 = next(r for r in results if "g_step1" in (r.id or ""))
    assert g1.status == Status.FAIL
    assert g1.continue_on_error is True


@pytest.mark.asyncio
async def test_group_stops_without_continue_on_error():
    """A group stops at a failed step when continue-on-error is not set."""
    runner = _make_runner()
    _setup_session(runner)

    scenario = ScenarioDefinition(
        name="test",
        groups={
            "my_group": GroupDefinition(
                steps=[
                    StepDefinition(step="g_step1", id="g_step1"),
                    StepDefinition(step="g_step2", id="g_step2"),
                ],
            ),
        },
        steps=[
            StepDefinition(step="my_group", id="run_group"),
        ],
    )

    call_order = []

    async def fake_execute(step, loop_context=None):
        call_order.append(step.id)
        if step.step == "g_step1":
            result = StepResult(id=step.id, name=step.step, status=Status.FAIL, duration=0.1, error_message="boom")
        else:
            result = StepResult(id=step.id, name=step.step, status=Status.PASS, duration=0.1)
        with runner.session_context:
            runner.session_context.update_result(result)
        return result

    with patch.object(runner, "execute_single_step", side_effect=fake_execute):
        with patch.object(runner, "initialize_session", new_callable=AsyncMock):
            with patch.object(runner, "_wait_for_dependencies", new_callable=AsyncMock):
                await runner.run_scenario(scenario)

    assert "g_step1" in call_order
    assert "g_step2" not in call_order, "g_step2 should NOT execute after g_step1 failure"
