"""
Allure reporter that writes scenario results as Allure test-case JSON.

Uses ``allure-python-commons`` lifecycle API (v2.x) to produce results
consumable by Allure CLI v3 (``allure generate``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from allure_commons._allure import plugin_manager
from allure_commons.lifecycle import AllureLifecycle
from allure_commons.logger import AllureFileLogger
from allure_commons.model2 import (
    Label,
    Parameter,
    StatusDetails,
)
from allure_commons.model2 import (
    Status as AllureStatus,
)
from allure_commons.types import AttachmentType, LabelType
from allure_commons.utils import now
from loguru import logger

if TYPE_CHECKING:
    from openutm_verification.core.reporting.http_collector import HttpExchange
    from openutm_verification.core.reporting.reporting_models import (
        ScenarioResult,
        Status,
        StepResult,
    )


def _map_status(status: Status) -> AllureStatus:
    """Map our Status enum to Allure's Status."""
    from openutm_verification.core.reporting.reporting_models import Status as OurStatus

    return {
        OurStatus.PASS: AllureStatus.PASSED,
        OurStatus.FAIL: AllureStatus.FAILED,
        OurStatus.SKIP: AllureStatus.SKIPPED,
        OurStatus.RUNNING: AllureStatus.BROKEN,
        OurStatus.WAITING: AllureStatus.BROKEN,
    }.get(status, AllureStatus.UNKNOWN)


def _ms(seconds: float) -> int:
    """Convert seconds → milliseconds (int)."""
    return int(seconds * 1000)


# Matches loop-iteration IDs like "submit_telemetry[0]", "group[3]"
_LOOP_ID_RE = re.compile(r"^(.+)\[(\d+)\]$")


def _is_loop_iteration(step_id: str | None) -> bool:
    return bool(step_id and _LOOP_ID_RE.match(step_id))


def _loop_base_id(step_id: str) -> str:
    m = _LOOP_ID_RE.match(step_id)
    return m.group(1) if m else step_id


def _loop_index(step_id: str) -> int:
    m = _LOOP_ID_RE.match(step_id)
    return int(m.group(2)) if m else 0


class AllureScenarioReporter:
    """Write Allure results for each scenario execution.

    Each instance registers its file logger under a unique plugin name so
    multiple reporters can coexist (e.g. concurrent server requests, or a
    failed instance that hasn't been closed yet). Use as a context manager to
    guarantee the plugin is unregistered::

        with AllureScenarioReporter(results_dir) as reporter:
            reporter.start_scenario(...)
            ...
    """

    def __init__(self, results_dir: str | Path) -> None:
        self._results_dir = Path(results_dir)
        self._results_dir.mkdir(parents=True, exist_ok=True)

        self._plugin_name = f"allure_scenario_file_logger_{uuid4().hex}"
        self._file_logger = AllureFileLogger(str(self._results_dir))
        plugin_manager.register(self._file_logger, self._plugin_name)

        self._lifecycle = AllureLifecycle()
        # Track current test case UUID for step nesting
        self._current_test_uuid: str | None = None
        self._closed = False

    # ── Context manager ───────────────────────────────────────────

    def __enter__(self) -> "AllureScenarioReporter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # ── Public API ────────────────────────────────────────────────

    def start_scenario(self, name: str, suite_name: str | None = None) -> None:
        """Begin a new Allure test case for the given scenario."""
        test_uuid = str(uuid4())
        self._current_test_uuid = test_uuid

        with self._lifecycle.schedule_test_case(uuid=test_uuid) as test_result:
            test_result.name = name
            test_result.fullName = f"{suite_name}.{name}" if suite_name else name
            test_result.start = now()
            test_result.labels = [
                Label(name=LabelType.FRAMEWORK, value="openutm-verification"),
                Label(name=LabelType.LANGUAGE, value="python"),
            ]
            if suite_name:
                test_result.labels.append(Label(name=LabelType.SUITE, value=suite_name))

    def record_steps(self, steps: list[StepResult[Any]]) -> None:
        """Record all steps, grouping consecutive loop iterations as substeps."""
        if self._current_test_uuid is None:
            logger.warning("record_steps called without an active scenario")
            return

        i = 0
        while i < len(steps):
            step = steps[i]

            # Check if this is the start of a loop iteration run
            if _is_loop_iteration(step.id):
                base_id = _loop_base_id(step.id)
                # Collect all consecutive iterations with the same base ID
                group: list[StepResult[Any]] = [step]
                j = i + 1
                while j < len(steps) and steps[j].id and _loop_base_id(steps[j].id) == base_id:
                    group.append(steps[j])
                    j += 1
                self._record_loop_step(step.name, group)
                i = j
            else:
                self._record_single_step(step, parent_uuid=self._current_test_uuid)
                i += 1

    def record_step(
        self,
        step_result: StepResult[Any],
        http_exchanges: list[HttpExchange] | None = None,
    ) -> None:
        """Record a single step (backwards-compatible entry point)."""
        if self._current_test_uuid is None:
            logger.warning("record_step called without an active scenario")
            return
        self._record_single_step(step_result, parent_uuid=self._current_test_uuid, http_exchanges=http_exchanges)

    def end_scenario(self, scenario_result: ScenarioResult) -> None:
        """Finalise the Allure test case for the scenario."""
        if self._current_test_uuid is None:
            return

        with self._lifecycle.update_test_case(uuid=self._current_test_uuid) as test_result:
            test_result.status = _map_status(scenario_result.status)
            test_result.stop = now()

            if scenario_result.error_message:
                test_result.statusDetails = StatusDetails(message=scenario_result.error_message)

        self._lifecycle.write_test_case(uuid=self._current_test_uuid)
        self._current_test_uuid = None

    def close(self) -> None:
        """Unregister the file logger plugin. Idempotent."""
        if self._closed:
            return
        self._closed = True
        try:
            plugin_manager.unregister(name=self._plugin_name)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"Allure plugin unregister failed for {self._plugin_name}: {exc}")

    # ── Internal ──────────────────────────────────────────────────

    def _record_loop_step(self, step_name: str, iterations: list[StepResult[Any]]) -> None:
        """Create a parent step with one substep per iteration."""
        parent_uuid = str(uuid4())

        # Determine aggregate status: FAIL if any failed, else PASS
        from openutm_verification.core.reporting.reporting_models import Status as OurStatus

        has_failure = any(s.status == OurStatus.FAIL for s in iterations)
        aggregate_status = OurStatus.FAIL if has_failure else OurStatus.PASS
        total_duration = sum(s.duration for s in iterations)

        with self._lifecycle.start_step(parent_uuid=self._current_test_uuid, uuid=parent_uuid) as parent_step:
            parent_step.name = f"{step_name} ({len(iterations)} iterations)"
            parent_step.start = now() - _ms(total_duration)
            parent_step.status = _map_status(aggregate_status)
            parent_step.parameters = [Parameter(name="iterations", value=str(len(iterations)))]

        # Record each iteration as a substep
        for idx, iteration_result in enumerate(iterations):
            self._record_single_step(
                iteration_result,
                parent_uuid=parent_uuid,
                label=f"[{idx}] {step_name}",
            )

        self._lifecycle.stop_step(uuid=parent_uuid)

    def _record_single_step(
        self,
        step_result: StepResult[Any],
        *,
        parent_uuid: str,
        http_exchanges: list[HttpExchange] | None = None,
        label: str | None = None,
    ) -> None:
        """Record one step with attachments in order: request, response, logs."""
        step_uuid = str(uuid4())
        with self._lifecycle.start_step(parent_uuid=parent_uuid, uuid=step_uuid) as step:
            step.name = label or step_result.name
            step.start = now() - _ms(step_result.duration)
            step.status = _map_status(step_result.status)

            if step_result.error_message:
                step.statusDetails = StatusDetails(message=step_result.error_message)

            if step_result.id:
                step.parameters = [Parameter(name="id", value=step_result.id)]

        # Each HTTP exchange becomes a substep with request/response attachments
        exchanges = http_exchanges or step_result.http_exchanges
        for i, exchange in enumerate(exchanges or []):
            idx = f"[{i + 1}] " if len(exchanges or []) > 1 else ""
            ex_uuid = str(uuid4())
            ex_status = AllureStatus.PASSED if exchange.response_status and exchange.response_status < 400 else AllureStatus.FAILED

            with self._lifecycle.start_step(parent_uuid=step_uuid, uuid=ex_uuid) as ex_step:
                ex_step.name = f"{idx}{exchange.method} {exchange.url} → {exchange.response_status}"
                ex_step.start = now() - int(exchange.duration_ms)
                ex_step.status = ex_status

            self._attach_json(
                ex_uuid,
                "Request",
                {
                    "method": exchange.method,
                    "url": exchange.url,
                    "headers": exchange.request_headers,
                    "body": exchange.request_body,
                },
            )

            self._attach_json(
                ex_uuid,
                "Response",
                {
                    "status": exchange.response_status,
                    "headers": exchange.response_headers,
                    "body": exchange.response_body,
                    "duration_ms": round(exchange.duration_ms, 2),
                    "error": exchange.error,
                },
            )

            self._lifecycle.stop_step(uuid=ex_uuid)

        if step_result.result is not None:
            self._attach_json(step_uuid, "Step Result", step_result.result)

        if step_result.logs:
            self._attach_text(step_uuid, "Logs", "".join(step_result.logs))

        self._lifecycle.stop_step(uuid=step_uuid)

    def _attach_json(self, parent_uuid: str, name: str, data: Any) -> None:
        """Attach a JSON blob to a step or test case."""
        try:
            body = json.dumps(data, indent=2, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            body = str(data)
        self._lifecycle.attach_data(
            uuid=str(uuid4()),
            body=body,
            name=name,
            attachment_type=AttachmentType.JSON,
            extension="json",
            parent_uuid=parent_uuid,
        )

    def _attach_text(self, parent_uuid: str, name: str, text: str) -> None:
        """Attach plain text to a step or test case."""
        self._lifecycle.attach_data(
            uuid=str(uuid4()),
            body=text,
            name=name,
            attachment_type=AttachmentType.TEXT,
            extension="txt",
            parent_uuid=parent_uuid,
        )
