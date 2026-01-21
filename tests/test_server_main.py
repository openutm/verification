from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

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
