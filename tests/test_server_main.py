from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from openutm_verification.server import router as router_module
from openutm_verification.server.main import app, get_session_manager

client = TestClient(app)


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200

    # If static files are mounted, we get HTML. If not, we get JSON.
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        assert "<!doctype html>" in response.text.lower()
    else:
        json_response = response.json()
        assert "message" in json_response
        assert "OpenUTM Verification API is running" in json_response["message"]


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_get_operations():
    mock_runner = MagicMock()
    mock_runner.get_available_operations.return_value = ["op1", "op2"]

    app.dependency_overrides[get_session_manager] = lambda: mock_runner

    try:
        response = client.get("/operations")
        assert response.status_code == 200
        assert response.json() == ["op1", "op2"]
    finally:
        app.dependency_overrides = {}


def test_reset_session():
    mock_runner = MagicMock()
    mock_runner.close_session = AsyncMock()
    mock_runner.initialize_session = AsyncMock()

    app.dependency_overrides[get_session_manager] = lambda: mock_runner

    try:
        response = client.post("/session/reset")
        assert response.status_code == 200
        assert response.json() == {"status": "session_reset"}

        mock_runner.close_session.assert_called_once()
        mock_runner.initialize_session.assert_called_once()
    finally:
        app.dependency_overrides = {}


def test_stop_scenario_when_running():
    """Test that /stop-scenario correctly calls runner.stop_scenario() and returns expected format."""
    mock_runner = MagicMock()
    mock_runner.stop_scenario = AsyncMock(return_value=True)

    app.dependency_overrides[get_session_manager] = lambda: mock_runner

    try:
        response = client.post("/stop-scenario")
        assert response.status_code == 200
        assert response.json() == {"stopped": True}

        mock_runner.stop_scenario.assert_called_once()
    finally:
        app.dependency_overrides = {}


def test_stop_scenario_when_not_running():
    """Test that /stop-scenario returns stopped=False when no scenario is running."""
    mock_runner = MagicMock()
    mock_runner.stop_scenario = AsyncMock(return_value=False)

    app.dependency_overrides[get_session_manager] = lambda: mock_runner

    try:
        response = client.post("/stop-scenario")
        assert response.status_code == 200
        assert response.json() == {"stopped": False}

        mock_runner.stop_scenario.assert_called_once()
    finally:
        app.dependency_overrides = {}


# ── /api/allure/* route tests ────────────────────────────────────────


def _install_runner(monkeypatch_or_app, runner) -> None:
    """Install a fake runner on the FastAPI app state for route tests."""
    monkeypatch_or_app.state.runner = runner


@pytest.fixture
def fake_runner(tmp_path):
    """Build a SessionManager-shaped MagicMock pointing at a tmp output dir."""
    runner = MagicMock()
    runner.config = MagicMock()
    runner.config.reporting = MagicMock()
    runner.config.reporting.output_dir = str(tmp_path)
    runner.config.reporting.timestamp_subdir = "2026_04_25T10_00_00"
    runner.config.reporting.allure = MagicMock()
    runner.config.reporting.allure.enabled = True
    runner.config.reporting.allure.results_dir = "allure-results"
    runner.current_timestamp_str = "2026_04_25T10_00_00"
    return runner


def test_allure_generate_disabled_returns_400(fake_runner):
    fake_runner.config.reporting.allure.enabled = False
    original = app.state.runner if hasattr(app.state, "runner") else None
    try:
        app.state.runner = fake_runner
        response = client.post("/api/allure/generate")
        assert response.status_code == 400
        assert "not enabled" in response.json()["detail"].lower()
    finally:
        if original is not None:
            app.state.runner = original


def test_allure_generate_missing_results_returns_404(fake_runner):
    original = app.state.runner if hasattr(app.state, "runner") else None
    try:
        app.state.runner = fake_runner
        response = client.post("/api/allure/generate")
        assert response.status_code == 404
        assert "no allure results" in response.json()["detail"].lower()
    finally:
        if original is not None:
            app.state.runner = original


def test_allure_generate_path_outside_output_dir_rejected(fake_runner, tmp_path, monkeypatch):
    # Configure absolute results_dir entirely outside the configured output_dir
    elsewhere = tmp_path.parent / "outside-results"
    elsewhere.mkdir(exist_ok=True)
    (elsewhere / "marker.json").write_text("{}", encoding="utf-8")
    fake_runner.config.reporting.allure.results_dir = str(elsewhere)

    # Force the CLI lookup so we don't depend on host setup
    monkeypatch.setattr(router_module.shutil, "which", lambda _name: "/usr/local/bin/allure")

    original = app.state.runner if hasattr(app.state, "runner") else None
    try:
        app.state.runner = fake_runner
        response = client.post("/api/allure/generate")
        assert response.status_code == 400
        assert "outside" in response.json()["detail"].lower()
    finally:
        if original is not None:
            app.state.runner = original
        elsewhere.joinpath("marker.json").unlink(missing_ok=True)
        elsewhere.rmdir()


def test_allure_generate_cli_failure_returns_500(fake_runner, tmp_path, monkeypatch):
    # Create a fake results dir with at least one file
    results_dir = tmp_path / fake_runner.current_timestamp_str / "allure-results"
    results_dir.mkdir(parents=True)
    (results_dir / "result.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(router_module.shutil, "which", lambda _name: "/usr/local/bin/allure")

    class _FakeProc:
        returncode = 1

        async def communicate(self):
            return (b"", b"boom: cli error")

    async def _fake_create_subprocess_exec(*_args, **_kwargs):
        return _FakeProc()

    monkeypatch.setattr(router_module.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    original = app.state.runner if hasattr(app.state, "runner") else None
    try:
        app.state.runner = fake_runner
        response = client.post("/api/allure/generate")
        assert response.status_code == 500
        assert "boom" in response.json()["detail"].lower()
    finally:
        if original is not None:
            app.state.runner = original


def test_allure_generate_success_returns_report_url(fake_runner, tmp_path, monkeypatch):
    results_dir = tmp_path / fake_runner.current_timestamp_str / "allure-results"
    results_dir.mkdir(parents=True)
    (results_dir / "result.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(router_module.shutil, "which", lambda _name: "/usr/local/bin/allure")

    class _FakeProc:
        returncode = 0

        async def communicate(self):
            return (b"ok", b"")

    async def _fake_create_subprocess_exec(*_args, **_kwargs):
        return _FakeProc()

    monkeypatch.setattr(router_module.asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    original = app.state.runner if hasattr(app.state, "runner") else None
    try:
        app.state.runner = fake_runner
        response = client.post("/api/allure/generate")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["report_url"].endswith("/allure-report/index.html")
        assert fake_runner.current_timestamp_str in body["report_url"]
    finally:
        if original is not None:
            app.state.runner = original


def test_allure_report_404_when_not_generated(fake_runner):
    original = app.state.runner if hasattr(app.state, "runner") else None
    try:
        app.state.runner = fake_runner
        response = client.get("/api/allure/report", follow_redirects=False)
        assert response.status_code == 404
    finally:
        if original is not None:
            app.state.runner = original


def test_allure_report_disabled_returns_400(fake_runner):
    fake_runner.config.reporting.allure.enabled = False
    original = app.state.runner if hasattr(app.state, "runner") else None
    try:
        app.state.runner = fake_runner
        response = client.get("/api/allure/report", follow_redirects=False)
        assert response.status_code == 400
    finally:
        if original is not None:
            app.state.runner = original


def test_allure_report_redirects_when_present(fake_runner, tmp_path):
    report_dir = tmp_path / fake_runner.current_timestamp_str / "allure-report"
    report_dir.mkdir(parents=True)
    (report_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    original = app.state.runner if hasattr(app.state, "runner") else None
    try:
        app.state.runner = fake_runner
        response = client.get("/api/allure/report", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"].endswith("/allure-report/index.html")
        assert fake_runner.current_timestamp_str in response.headers["location"]
    finally:
        if original is not None:
            app.state.runner = original
