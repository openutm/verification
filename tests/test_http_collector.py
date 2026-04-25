"""Tests for the opt-in HTTP exchange collector."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

import pytest

from openutm_verification.core.reporting import http_collector
from openutm_verification.core.reporting.http_collector import (
    _MAX_BODY_SIZE,
    HttpCollector,
    HttpExchange,
    _sanitise_body,
    _sanitise_headers,
    _truncate_request_body,
)


@pytest.fixture(autouse=True)
def _reset_collector() -> Any:
    """Ensure each test starts with capture disabled and a clean scope."""
    HttpCollector.set_enabled(False)
    http_collector._collector_state.set(None)
    yield
    HttpCollector.set_enabled(False)
    http_collector._collector_state.set(None)


def _fake_response(status: int = 200, body: str = "{}", headers: dict[str, str] | None = None) -> Any:
    return SimpleNamespace(
        status_code=status,
        headers=headers or {"content-type": "application/json"},
        text=body,
    )


def test_disabled_collector_is_a_noop() -> None:
    HttpCollector.init()  # disabled, should not allocate state
    HttpCollector.record_from_httpx(
        method="GET",
        url="http://example/",
        request_headers={"authorization": "Bearer secret"},
        request_body={"password": "p"},
        response=_fake_response(),
        start=time.time(),
    )
    assert HttpCollector.drain() == []


def test_enabled_capture_records_and_drains() -> None:
    HttpCollector.set_enabled(True)
    HttpCollector.init()
    HttpCollector.record_from_httpx(
        method="POST",
        url="http://api/",
        request_headers={"content-type": "application/json"},
        request_body={"a": 1},
        response=_fake_response(status=201, body='{"ok": true}'),
        start=time.time(),
    )

    drained = HttpCollector.drain()
    assert len(drained) == 1
    assert isinstance(drained[0], HttpExchange)
    assert drained[0].response_status == 201
    # drain resets the scope
    assert HttpCollector.drain() == []


def test_drain_without_init_returns_empty() -> None:
    HttpCollector.set_enabled(True)
    assert HttpCollector.drain() == []


def test_sensitive_headers_are_masked() -> None:
    out = _sanitise_headers(
        {
            "Authorization": "Bearer abc.def.ghi",
            "Cookie": "session=xyz",
            "X-API-Key": "topsecret",
            "Content-Type": "application/json",
        }
    )
    assert out["Authorization"].endswith("***")
    assert out["Cookie"] == "***"
    assert out["X-API-Key"] == "***"
    assert out["Content-Type"] == "application/json"


def test_recursive_body_redaction() -> None:
    body = {
        "user": "alice",
        "Password": "p1",
        "nested": {"access_token": "tk", "items": [{"refresh_token": "rt", "kept": "ok"}]},
        "list": [{"client_secret": "cs"}, {"safe": 1}],
    }
    cleaned = _sanitise_body(body)
    assert cleaned["user"] == "alice"
    assert cleaned["Password"] == "***"
    assert cleaned["nested"]["access_token"] == "***"
    assert cleaned["nested"]["items"][0]["refresh_token"] == "***"
    assert cleaned["nested"]["items"][0]["kept"] == "ok"
    assert cleaned["list"][0]["client_secret"] == "***"
    assert cleaned["list"][1]["safe"] == 1
    # Original is untouched
    assert body["Password"] == "p1"


def test_request_body_truncation_for_oversized_string() -> None:
    big = "x" * (_MAX_BODY_SIZE + 50)
    out = _truncate_request_body(big)
    assert isinstance(out, str)
    assert "[truncated" in out
    assert len(out) < _MAX_BODY_SIZE + 100


def test_request_body_truncation_for_oversized_structured_payload() -> None:
    big_struct = {"items": ["x" * 1000 for _ in range(500)]}  # > 100 KB serialised
    out = _truncate_request_body(big_struct)
    assert isinstance(out, str)
    assert "[truncated" in out


def test_small_structured_request_body_kept_as_is() -> None:
    body = {"a": 1}
    assert _truncate_request_body(body) is body


def test_record_from_httpx_sanitises_and_truncates() -> None:
    HttpCollector.set_enabled(True)
    HttpCollector.init()
    HttpCollector.record_from_httpx(
        method="POST",
        url="http://api/login",
        request_headers={"Authorization": "Bearer secret-token"},
        request_body={"password": "hunter2", "user": "alice"},
        response=_fake_response(body="z" * (_MAX_BODY_SIZE + 200)),
        start=time.time(),
    )
    [exchange] = HttpCollector.drain()
    assert exchange.request_headers["Authorization"].endswith("***")
    assert exchange.request_body == {"password": "***", "user": "alice"}
    assert exchange.response_body and "[truncated" in exchange.response_body


def test_error_field_is_recorded() -> None:
    HttpCollector.set_enabled(True)
    HttpCollector.init()
    HttpCollector.record_from_httpx(
        method="GET",
        url="http://api/",
        request_headers={},
        request_body=None,
        response=None,
        start=time.time(),
        error="ConnectError: refused",
    )
    [exchange] = HttpCollector.drain()
    assert exchange.error == "ConnectError: refused"
    assert exchange.response_status is None
