from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from openutm_verification.core.clients.flight_blender.base_client import BaseBlenderAPIClient
from openutm_verification.models import FlightBlenderError

BASE_URL = "https://example.com"


def make_client(with_token: bool = True) -> BaseBlenderAPIClient:
    creds = {"access_token": "token123"} if with_token else {}
    return BaseBlenderAPIClient(base_url=BASE_URL, credentials=creds)


def test_init_with_credentials_sets_auth_header():
    client = make_client(with_token=True)
    assert client.client.headers["Content-Type"] == "application/json"
    assert client.client.headers["Authorization"] == "Bearer token123"


def test_init_without_credentials_has_no_auth_header():
    client = make_client(with_token=False)
    assert client.client.headers["Content-Type"] == "application/json"
    assert "Authorization" not in client.client.headers


@patch("openutm_verification.core.clients.flight_blender.base_client.httpx.AsyncClient")
async def test_request_success(mock_client_cls: MagicMock):
    mock_client = AsyncMock()
    # headers should be a MagicMock (sync) because .update() is sync
    mock_client.headers = MagicMock()

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_client.request.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    client = make_client()
    # We need to replace the client created in __init__ with our mock
    # because __init__ calls httpx.AsyncClient() which is mocked by the patch
    # but we want to control the instance.
    # Actually, mock_client_cls.return_value = mock_client handles the instantiation return.

    resp = await client.get("/path")

    mock_client.request.assert_called_once_with("GET", f"{BASE_URL}/path", json=None)
    mock_resp.raise_for_status.assert_called_once()
    assert resp is mock_resp


@patch("openutm_verification.core.clients.flight_blender.base_client.httpx.AsyncClient")
async def test_request_http_status_error_raises_flight_blender_error(mock_client_cls: MagicMock):
    mock_client = AsyncMock()
    mock_client.headers = MagicMock()
    mock_client_cls.return_value = mock_client

    req = httpx.Request("GET", f"{BASE_URL}/path")
    resp = httpx.Response(400, request=req, text="bad request")
    error = httpx.HTTPStatusError("boom", request=req, response=resp)

    mock_resp = MagicMock(spec=httpx.Response)
    # Simulate raise_for_status raising HTTPStatusError with attached response
    mock_resp.raise_for_status.side_effect = error
    mock_resp.status_code = 400
    mock_resp.text = "bad request"
    mock_client.request.return_value = mock_resp

    client = make_client()

    with pytest.raises(FlightBlenderError) as ei:
        await client.get("/path")

    assert "Request failed: 400" in str(ei.value)


@patch("openutm_verification.core.clients.flight_blender.base_client.httpx.AsyncClient")
async def test_request_request_error_raises_flight_blender_error(mock_client_cls: MagicMock):
    mock_client = AsyncMock()
    mock_client.headers = MagicMock()
    mock_client_cls.return_value = mock_client

    req = httpx.Request("GET", f"{BASE_URL}/path")
    mock_client.request.side_effect = httpx.RequestError("network issue", request=req)

    client = make_client()

    with pytest.raises(FlightBlenderError) as ei:
        await client.get("/path")

    assert "Request failed" in str(ei.value)


@patch.object(BaseBlenderAPIClient, "_request")
async def test_http_verbs_delegate_to_request(mock_request: AsyncMock):
    client = make_client()

    await client.get("/g", silent_status=[204])
    await client.post("/p", json={"a": 1}, silent_status=[201])
    await client.put("/u", json={"b": 2})
    await client.delete("/d")

    assert mock_request.call_count == 4
    mock_request.assert_any_call("GET", "/g", silent_status=[204])
    mock_request.assert_any_call("POST", "/p", json={"a": 1}, silent_status=[201])
    mock_request.assert_any_call("PUT", "/u", json={"b": 2}, silent_status=None)
    mock_request.assert_any_call("DELETE", "/d", silent_status=None)


@pytest.mark.asyncio
@patch("openutm_verification.core.clients.flight_blender.base_client.connect", new_callable=AsyncMock)
async def test_create_websocket_connection_sends_auth(mock_connect: AsyncMock):
    ws = AsyncMock()
    mock_connect.return_value = ws

    client = make_client(with_token=True)
    conn = await client.create_websocket_connection("/ws")

    mock_connect.assert_called_once_with("wss://example.com/ws")
    ws.send.assert_called_once_with("Bearer token123")
    assert conn is ws


@pytest.mark.asyncio
@patch("openutm_verification.core.clients.flight_blender.base_client.connect", new_callable=AsyncMock)
async def test_create_websocket_connection_no_auth_does_not_send(mock_connect: AsyncMock):
    ws = AsyncMock()
    mock_connect.return_value = ws

    client = make_client(with_token=False)
    await client.create_websocket_connection("/ws")

    mock_connect.assert_called_once_with("wss://example.com/ws")
    ws.send.assert_not_called()


@pytest.mark.asyncio
@patch("openutm_verification.core.clients.flight_blender.base_client.connect", new_callable=AsyncMock)
async def test_create_websocket_connection_refused_raises(mock_connect: AsyncMock):
    mock_connect.side_effect = ConnectionRefusedError
    client = make_client()
    with pytest.raises(FlightBlenderError):
        await client.create_websocket_connection("/ws")


@pytest.mark.asyncio
async def test_close_websocket_connection_calls_close():
    client = make_client()
    ws = AsyncMock()
    await client.close_websocket_connection(ws)
    ws.close.assert_called_once()
