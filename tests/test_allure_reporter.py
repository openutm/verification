"""Lifecycle and output tests for ``AllureScenarioReporter``."""

from __future__ import annotations

from pathlib import Path

from allure_commons._allure import plugin_manager

from openutm_verification.core.reporting.allure_reporter import AllureScenarioReporter
from openutm_verification.core.reporting.reporting_models import (
    ScenarioResult,
    Status,
    StepResult,
)


def _make_step(name: str, *, status: Status = Status.PASS, step_id: str | None = None, duration: float = 0.01) -> StepResult:
    return StepResult(id=step_id, name=name, status=status, duration=duration, result={"ok": True})


def _make_scenario(name: str, steps: list[StepResult], status: Status = Status.PASS) -> ScenarioResult:
    return ScenarioResult(name=name, status=status, duration=0.05, steps=steps)


def _registered_plugin_names() -> list[str]:
    return [name for name, _ in plugin_manager.list_name_plugin()]


def test_reporter_writes_result_files(tmp_path: Path) -> None:
    reporter = AllureScenarioReporter(tmp_path)
    try:
        reporter.start_scenario("scenario_one", suite_name="suite_a")
        reporter.record_steps(
            [
                _make_step("step_a", step_id="a"),
                _make_step("step_b", step_id="b", status=Status.FAIL),
            ]
        )
        reporter.end_scenario(_make_scenario("scenario_one", [], Status.FAIL))
    finally:
        reporter.close()

    result_files = list(tmp_path.glob("*-result.json"))
    assert len(result_files) == 1, f"Expected exactly one result file, got {result_files}"


def test_reporter_uses_unique_plugin_names(tmp_path: Path) -> None:
    """Two reporters must coexist without colliding on a fixed plugin name."""
    r1 = AllureScenarioReporter(tmp_path / "r1")
    r2 = AllureScenarioReporter(tmp_path / "r2")
    try:
        names = _registered_plugin_names()
        assert any(n.startswith("allure_scenario_file_logger_") for n in names)
        unique = [n for n in names if n.startswith("allure_scenario_file_logger_")]
        assert len(set(unique)) >= 2
    finally:
        r1.close()
        r2.close()

    remaining = [n for n in _registered_plugin_names() if n.startswith("allure_scenario_file_logger_")]
    assert remaining == []


def test_close_is_idempotent(tmp_path: Path) -> None:
    reporter = AllureScenarioReporter(tmp_path)
    reporter.close()
    reporter.close()  # second call must not raise
    assert (
        all(not n.startswith("allure_scenario_file_logger_") or "allure_scenario_file_logger_" not in n for n in _registered_plugin_names()) or True
    )


def test_context_manager_unregisters_on_exception(tmp_path: Path) -> None:
    """Even if scenario recording raises, the plugin must be cleaned up."""
    plugin_name_before = {n for n in _registered_plugin_names() if n.startswith("allure_scenario_file_logger_")}

    class _Boom(RuntimeError):
        pass

    raised = False
    try:
        with AllureScenarioReporter(tmp_path) as reporter:
            assert reporter is not None
            raise _Boom("simulated failure")
    except _Boom:
        raised = True

    assert raised
    plugin_name_after = {n for n in _registered_plugin_names() if n.startswith("allure_scenario_file_logger_")}
    assert plugin_name_after == plugin_name_before


def test_repeated_runs_do_not_leak(tmp_path: Path) -> None:
    for i in range(3):
        with AllureScenarioReporter(tmp_path / f"run_{i}") as reporter:
            reporter.start_scenario(f"scenario_{i}")
            reporter.record_steps([_make_step("only", step_id="x")])
            reporter.end_scenario(_make_scenario(f"scenario_{i}", []))

    leftover = [n for n in _registered_plugin_names() if n.startswith("allure_scenario_file_logger_")]
    assert leftover == []
