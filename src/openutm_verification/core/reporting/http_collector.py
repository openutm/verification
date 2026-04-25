"""
Context-variable based HTTP exchange collector.

Captures HTTP request/response data during scenario step execution so it can
be attached to Allure reports. Uses the same ``contextvars`` pattern as
``_scenario_state`` in :mod:`scenario_runner`.

Capture is opt-in: callers must enable it via :meth:`HttpCollector.set_enabled`
(typically driven by ``config.reporting.allure.capture_http``). When disabled,
all methods are no-ops and bodies/headers are never retained in memory.
"""

from __future__ import annotations

import contextvars
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

# Bodies are always truncated above this length. Applied to both request and
# response payloads after JSON serialisation.
_MAX_BODY_SIZE = 100_000

# Mask these JSON body keys (case-insensitive) recursively before storing.
_SENSITIVE_BODY_KEYS = frozenset(
    {
        "authorization",
        "access_token",
        "refresh_token",
        "id_token",
        "token",
        "client_secret",
        "password",
        "secret",
        "cookie",
        "set-cookie",
        "api_key",
        "apikey",
        "x-api-key",
    }
)


@dataclass(frozen=True)
class HttpExchange:
    """A single HTTP request/response pair."""

    method: str
    url: str
    request_headers: dict[str, str]
    request_body: Any  # JSON-serialisable payload (sanitised, truncated) or None
    response_status: int | None
    response_headers: dict[str, str]
    response_body: str | None
    duration_ms: float
    error: str | None = None


# ── Sanitisation helpers ─────────────────────────────────────────────

_BEARER_RE = re.compile(r"(Bearer\s+)\S+", re.IGNORECASE)
_SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "set-cookie", "x-api-key", "x-api-token", "proxy-authorization"})


def _sanitise_headers(headers: dict[str, str]) -> dict[str, str]:
    """Mask sensitive header values."""
    out: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in _SENSITIVE_HEADERS:
            out[k] = _BEARER_RE.sub(r"\1***", v) if "bearer" in v.lower() else "***"
        else:
            out[k] = v
    return out


def _sanitise_body(body: Any) -> Any:
    """Recursively replace values for sensitive keys with ``"***"``.

    Only inspects ``dict``/``list`` structures; primitives and other types are
    returned unchanged. The original input is not mutated.
    """
    if isinstance(body, dict):
        return {k: ("***" if k.lower() in _SENSITIVE_BODY_KEYS else _sanitise_body(v)) for k, v in body.items()}
    if isinstance(body, list):
        return [_sanitise_body(v) for v in body]
    return body


def _truncate(body: str | None) -> str | None:
    if body is None:
        return None
    if len(body) > _MAX_BODY_SIZE:
        return body[:_MAX_BODY_SIZE] + f"\n... [truncated, total {len(body)} chars]"
    return body


def _truncate_request_body(body: Any) -> Any:
    """Bound request body size after sanitisation.

    Strings are truncated directly. Structured payloads (``dict``/``list``)
    are JSON-serialised for size estimation; if they exceed the cap we
    replace them with a truncated string representation so memory usage stays
    bounded regardless of payload depth.
    """
    if body is None:
        return None
    if isinstance(body, str):
        return _truncate(body)
    try:
        serialised = json.dumps(body, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return _truncate(str(body))
    if len(serialised) <= _MAX_BODY_SIZE:
        return body
    return _truncate(serialised)


# ── Collector state ──────────────────────────────────────────────────


@dataclass
class _CollectorState:
    exchanges: list[HttpExchange] = field(default_factory=list)


_collector_state: contextvars.ContextVar[_CollectorState | None] = contextvars.ContextVar("_collector_state", default=None)


class HttpCollector:
    """Collect :class:`HttpExchange` instances for the current async context.

    Disabled by default. Call :meth:`set_enabled` once during config load to
    opt in. While disabled all class methods are cheap no-ops so the steady
    state imposes no overhead on production scenario runs.
    """

    _enabled: bool = False

    @classmethod
    def set_enabled(cls, enabled: bool) -> None:
        """Toggle global capture. Affects all subsequent ``init``/``record`` calls."""
        cls._enabled = bool(enabled)

    @classmethod
    def is_enabled(cls) -> bool:
        return cls._enabled

    @staticmethod
    def init() -> None:
        """Start a fresh collection scope (call once per step)."""
        if not HttpCollector._enabled:
            return
        _collector_state.set(_CollectorState())

    @staticmethod
    def record(exchange: HttpExchange) -> None:
        """Append an exchange to the current scope (no-op if not initialised)."""
        if not HttpCollector._enabled:
            return
        state = _collector_state.get()
        if state is not None:
            state.exchanges.append(exchange)

    @staticmethod
    def drain() -> list[HttpExchange]:
        """Return all collected exchanges and reset the scope."""
        state = _collector_state.get()
        if state is None:
            return []
        exchanges = state.exchanges
        _collector_state.set(None)
        return exchanges

    # Convenience: build + record from raw httpx objects ───────────────

    @staticmethod
    def record_from_httpx(
        *,
        method: str,
        url: str,
        request_headers: dict[str, str],
        request_body: Any,
        response: Any | None,
        start: float,
        error: str | None = None,
    ) -> None:
        """Build an :class:`HttpExchange` from httpx-style data and record it.

        Performs all sanitisation/truncation up-front so nothing sensitive or
        unbounded is retained even if the resulting exchange is later
        serialised to disk.
        """
        if not HttpCollector._enabled:
            return

        duration_ms = (time.time() - start) * 1000
        resp_status = getattr(response, "status_code", None) if response else None
        resp_headers = dict(response.headers) if response and hasattr(response, "headers") else {}
        resp_body: str | None = None
        if response is not None:
            try:
                resp_body = response.text
            except Exception:
                resp_body = "<unreadable>"

        exchange = HttpExchange(
            method=method,
            url=url,
            request_headers=_sanitise_headers(request_headers),
            request_body=_truncate_request_body(_sanitise_body(request_body)),
            response_status=resp_status,
            response_headers=_sanitise_headers(resp_headers),
            response_body=_truncate(resp_body),
            duration_ms=duration_ms,
            error=error,
        )
        HttpCollector.record(exchange)
