import json
from datetime import UTC, datetime
from pathlib import Path

from openutm_verification.core.execution.config_models import (
    AirTrafficSimulatorSettings,
    AppConfig,
    AuthConfig,
    DataFiles,
    DeploymentDetails,
    FlightBlenderConfig,
    OpenSkyConfig,
    ReportingConfig,
)
from openutm_verification.core.flight_phase import FlightPhase
from openutm_verification.core.reporting.reporting import create_report_data, generate_reports
from openutm_verification.core.reporting.reporting_models import ScenarioResult, Status, StepResult


def _make_app_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        version="1.0",
        run_id="test-run",
        flight_blender=FlightBlenderConfig(url="http://localhost:8000", auth=AuthConfig()),
        opensky=OpenSkyConfig(auth=AuthConfig()),
        air_traffic_simulator_settings=AirTrafficSimulatorSettings(
            number_of_aircraft=1, simulation_duration=1, single_or_multiple_sensors="single", sensor_ids=[]
        ),
        data_files=DataFiles(),
        suites={},
        reporting=ReportingConfig(output_dir=str(tmp_path), formats=["json", "html"], deployment_details=DeploymentDetails()),
    )


def test_report_outputs_use_result(tmp_path: Path):
    app_config = _make_app_config(tmp_path)

    # Build a simple scenario result with a single step
    step = StepResult(id="Generate UUID", name="Generate UUID", status=Status.PASS, duration=0.01, result={"uuid": "abc-123"})
    scenario_result = ScenarioResult(
        name="sample_scenario",
        suite_name=None,
        status=Status.PASS,
        duration=0.01,
        steps=[step],
        error_message=None,
        flight_declaration_filename=None,
        telemetry_filename=None,
        flight_declaration_data=None,
        flight_declaration_via_operational_intent_data=None,
        telemetry_data=None,
        air_traffic_data=None,
        visualization_2d_path=None,
        visualization_3d_path=None,
        docs=None,
    )

    report_data = create_report_data(
        config=app_config,
        config_path="config/default.yaml",
        results=[scenario_result],
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        run_id="test-run",
        docs_dir=None,
    )

    # Generate reports
    generate_reports(report_data, app_config.reporting, base_filename="report")

    # Assert JSON contains 'result' for steps and not 'details'
    json_path = next(tmp_path.rglob("report.json"))
    content = json.loads(json_path.read_text(encoding="utf-8"))
    assert "results" in content
    assert content["results"][0]["steps"][0].get("result") == {"uuid": "abc-123"}
    assert "details" not in content["results"][0]["steps"][0]

    # Check HTML contains 'Result' header and prints the uuid value
    html_path = next(tmp_path.rglob("report.html"))
    html = html_path.read_text(encoding="utf-8")
    assert "<th>Result</th>" in html
    assert "abc-123" in html


def test_report_html_groups_steps_by_phase(tmp_path: Path):
    app_config = _make_app_config(tmp_path)

    steps = [
        StepResult(id="s1", name="Setup geo fence", status=Status.PASS, duration=0.01, result={}, phase=FlightPhase.PRE_FLIGHT),
        StepResult(id="s2", name="Upload declaration", status=Status.PASS, duration=0.02, result={}, phase=FlightPhase.PRE_FLIGHT),
        StepResult(id="s3", name="Stream telemetry", status=Status.PASS, duration=1.0, result={}, phase=FlightPhase.CRUISE),
        StepResult(id="s4", name="Cleanup", status=Status.PASS, duration=0.01, result={}, phase=FlightPhase.POST_FLIGHT),
    ]
    scenario_result = ScenarioResult(
        name="phased_scenario",
        suite_name=None,
        status=Status.PASS,
        duration=1.04,
        steps=steps,
        error_message=None,
        flight_declaration_filename=None,
        telemetry_filename=None,
        flight_declaration_data=None,
        flight_declaration_via_operational_intent_data=None,
        telemetry_data=None,
        air_traffic_data=None,
        visualization_2d_path=None,
        visualization_3d_path=None,
        docs=None,
    )

    report_data = create_report_data(
        config=app_config,
        config_path="config/default.yaml",
        results=[scenario_result],
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        run_id="test-run",
        docs_dir=None,
    )
    generate_reports(report_data, app_config.reporting, base_filename="report")

    html_path = next(tmp_path.rglob("report.html"))
    html = html_path.read_text(encoding="utf-8")

    # Phase headers should appear with human-readable labels
    assert "Pre-flight" in html
    assert "Cruise" in html
    assert "Post-flight" in html

    # Phase badges should contain the phase values
    assert ">PRE FLIGHT<" in html
    assert ">CRUISE<" in html
    assert ">POST FLIGHT<" in html

    # All steps should be present
    assert "Setup geo fence" in html
    assert "Upload declaration" in html
    assert "Stream telemetry" in html
    assert "Cleanup" in html


def test_report_html_no_phases_renders_flat_table(tmp_path: Path):
    app_config = _make_app_config(tmp_path)

    steps = [
        StepResult(id="s1", name="Step A", status=Status.PASS, duration=0.01, result={}),
        StepResult(id="s2", name="Step B", status=Status.PASS, duration=0.02, result={}),
    ]
    scenario_result = ScenarioResult(
        name="flat_scenario",
        suite_name=None,
        status=Status.PASS,
        duration=0.03,
        steps=steps,
        error_message=None,
        flight_declaration_filename=None,
        telemetry_filename=None,
        flight_declaration_data=None,
        flight_declaration_via_operational_intent_data=None,
        telemetry_data=None,
        air_traffic_data=None,
        visualization_2d_path=None,
        visualization_3d_path=None,
        docs=None,
    )

    report_data = create_report_data(
        config=app_config,
        config_path="config/default.yaml",
        results=[scenario_result],
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        run_id="test-run",
        docs_dir=None,
    )
    generate_reports(report_data, app_config.reporting, base_filename="report")

    html_path = next(tmp_path.rglob("report.html"))
    html = html_path.read_text(encoding="utf-8")

    # No phase group headers in content (CSS rule may still exist in <style>)
    assert 'class="phase-header"' not in html
    # Steps still render
    assert "Step A" in html
    assert "Step B" in html


def test_report_html_mixed_phases_and_none(tmp_path: Path):
    """Regression: steps mixing phase=None and phase=<value> must not crash groupby."""
    app_config = _make_app_config(tmp_path)

    steps = [
        StepResult(id="s1", name="Setup", status=Status.PASS, duration=0.01, result={}, phase=FlightPhase.PRE_FLIGHT),
        StepResult(id="s2", name="Generate UUID", status=Status.PASS, duration=0.01, result={}),  # phase=None
        StepResult(id="s3", name="Stream", status=Status.PASS, duration=1.0, result={}, phase=FlightPhase.CRUISE),
        StepResult(id="s4", name="Cleanup", status=Status.PASS, duration=0.01, result={}),  # phase=None
    ]
    scenario_result = ScenarioResult(
        name="mixed_phases",
        suite_name=None,
        status=Status.PASS,
        duration=1.03,
        steps=steps,
        error_message=None,
        flight_declaration_filename=None,
        telemetry_filename=None,
        flight_declaration_data=None,
        flight_declaration_via_operational_intent_data=None,
        telemetry_data=None,
        air_traffic_data=None,
        visualization_2d_path=None,
        visualization_3d_path=None,
        docs=None,
    )

    report_data = create_report_data(
        config=app_config,
        config_path="config/default.yaml",
        results=[scenario_result],
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC),
        run_id="test-run",
        docs_dir=None,
    )

    # Must not raise TypeError from groupby sorting None vs str
    generate_reports(report_data, app_config.reporting, base_filename="report")

    html_path = next(tmp_path.rglob("report.html"))
    html = html_path.read_text(encoding="utf-8")

    # Phased steps grouped under phase headers
    assert "Pre-flight" in html
    assert "Cruise" in html
    # Unphased steps grouped under "Other Steps"
    assert "Other Steps" in html
    # All step names present
    assert "Setup" in html
    assert "Generate UUID" in html
    assert "Stream" in html
    assert "Cleanup" in html
