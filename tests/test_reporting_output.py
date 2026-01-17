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
from openutm_verification.core.reporting.reporting import create_report_data, generate_reports
from openutm_verification.core.reporting.reporting_models import ScenarioResult, Status, StepResult


def test_report_outputs_use_result(tmp_path: Path):
    # Minimal AppConfig
    app_config = AppConfig(
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
