"""
Context-variable based HTTP exchange collector.

Captures HTTP request/response data during scenario step execution so it can
be attached to Allure reports. Uses the same ``contextvars`` pattern as
``_scenario_state`` in :mod:`scenario_runner`.
"""

from __future__ import annotations

import contextvars
import re
import time
from dataclasses import dataclass, field
from typing import Any

_MAX_BODY_SIZE = 100_000  # truncate bodies larger than ~100 KB


@dataclass(frozen=True)
class HttpExchange:
    """A single HTTP request/response pair."""

    method: str
    url: str
    request_headers: dict[str, str]
    request_body: Any  # JSON-serialisable payload or None
    response_status: int | None
    response_headers: dict[str, str]
    response_body: str | None
    duration_ms: float
    error: str | None = None


# ── Sanitisation helpers ─────────────────────────────────────────────

_BEARER_RE = re.compile(r"(Bearer\s+)\S+", re.IGNORECASE)
_SENSITIVE_HEADERS = frozenset({"authorization", "cookie", "set-cookie", "x-api-key"})


def _sanitise_headers(headers: dict[str, str]) -> dict[str, str]:
    """Mask sensitive header values."""
    out: dict[str, str] = {}
    for k, v in headers.items():
        if k.lower() in _SENSITIVE_HEADERS:
            out[k] = _BEARER_RE.sub(r"\1***", v) if "bearer" in v.lower() else "***"
        else:
            out[k] = v
    return out


def _truncate(body: str | None) -> str | None:
    if body is None:
        return None
    if len(body) > _MAX_BODY_SIZE:
        return body[:_MAX_BODY_SIZE] + f"\n... [truncated, total {len(body)} chars]"
    return body


# ── Collector state ──────────────────────────────────────────────────


@dataclass
class _CollectorState:
    exchanges: list[HttpExchange] = field(default_factory=list)


_collector_state: contextvars.ContextVar[_CollectorState | None] = contextvars.ContextVar("_collector_state", default=None)


class HttpCollector:
    """Collect :class:`HttpExchange` instances for the current async context."""

    @staticmethod
    def init() -> None:
        """Start a fresh collection scope (call once per step)."""
        _collector_state.set(_CollectorState())

    @staticmethod
    def record(exchange: HttpExchange) -> None:
        """Append an exchange to the current scope (no-op if not initialised)."""
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
        """Build an :class:`HttpExchange` from httpx-style data and record it."""
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
            request_body=request_body,
            response_status=resp_status,
            response_headers=_sanitise_headers(resp_headers),
            response_body=_truncate(resp_body),
            duration_ms=duration_ms,
            error=error,
        )
        HttpCollector.record(exchange)
