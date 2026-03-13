"""Tests for flight phase annotations on scenario steps."""

import pytest

from openutm_verification.core.execution.scenario_runner import (
    ScenarioContext,
    ScenarioState,
    scenario_step,
)
from openutm_verification.core.flight_phase import FlightPhase
from openutm_verification.core.reporting.reporting_models import Status, StepResult


class DummyClient:
    """Minimal client class for testing phase propagation."""

    @scenario_step("Phase step", phase=FlightPhase.PRE_FLIGHT)
    async def step_with_phase(self):
        return {"ok": True}

    @scenario_step("No phase step")
    async def step_without_phase(self):
        return {"ok": True}

    @scenario_step("Returns StepResult", phase=FlightPhase.CRUISE)
    async def step_returning_step_result(self):
        return StepResult(name="Returns StepResult", status=Status.PASS, duration=0.0, result={"custom": True})

    @scenario_step("Returns StepResult with phase", phase=FlightPhase.CRUISE)
    async def step_returning_step_result_with_own_phase(self):
        return StepResult(
            name="Returns StepResult with phase", phase=FlightPhase.POST_FLIGHT, status=Status.PASS, duration=0.0, result={"custom": True}
        )


class TestPhaseIntrospection:
    """Tests that _step_phase metadata is correctly set on step wrappers."""

    def test_step_has_phase_metadata(self):
        method = DummyClient.step_with_phase
        assert getattr(method, "_step_phase", None) == FlightPhase.PRE_FLIGHT

    def test_step_without_phase_has_none_metadata(self):
        method = DummyClient.step_without_phase
        assert getattr(method, "_step_phase", None) is None

    def test_step_has_step_name_metadata(self):
        method = DummyClient.step_with_phase
        assert getattr(method, "_step_name", None) == "Phase step"

    def test_step_is_scenario_step(self):
        method = DummyClient.step_with_phase
        assert getattr(method, "_is_scenario_step", False) is True


class TestPhaseInStepResult:
    """Tests that phase is correctly propagated to StepResult."""

    @pytest.mark.asyncio
    async def test_raw_return_gets_phase(self):
        client = DummyClient()
        with ScenarioContext(ScenarioState(active=True)):
            result = await client.step_with_phase()
        assert result.phase == FlightPhase.PRE_FLIGHT

    @pytest.mark.asyncio
    async def test_raw_return_without_phase(self):
        client = DummyClient()
        with ScenarioContext(ScenarioState(active=True)):
            result = await client.step_without_phase()
        assert result.phase is None

    @pytest.mark.asyncio
    async def test_step_result_return_inherits_decorator_phase(self):
        """When step returns StepResult without phase, decorator phase is applied."""
        client = DummyClient()
        with ScenarioContext(ScenarioState(active=True)):
            result = await client.step_returning_step_result()
        assert result.phase == FlightPhase.CRUISE

    @pytest.mark.asyncio
    async def test_step_result_return_keeps_own_phase(self):
        """When step returns StepResult with its own phase, it is preserved."""
        client = DummyClient()
        with ScenarioContext(ScenarioState(active=True)):
            result = await client.step_returning_step_result_with_own_phase()
        assert result.phase == FlightPhase.POST_FLIGHT
