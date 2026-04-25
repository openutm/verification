"""Helpers for redacting secrets in config payloads served by the API.

The unauthenticated GUI/API must never echo real credentials back to clients.
``redact_auth`` and ``redact_amqp`` produce safe copies for ``GET /api/config``
responses; ``strip_redacted`` drops the placeholder on ``PUT /api/config`` so a
GET→PUT round-trip never overwrites the on-disk secret with the sentinel.
"""

from typing import Any

# Sentinel returned to the GUI in place of secret values. Non-empty (so users
# can tell the field is populated) but unmistakably not a real credential, and
# explicitly ignored by PUT /api/config so a round-trip never persists it.
REDACTED = "***REDACTED***"


def redact_auth(auth: dict[str, Any]) -> dict[str, Any]:
    """Redact secret fields in an AuthConfig dict (returns a shallow copy)."""
    redacted = dict(auth)
    if redacted.get("client_secret"):
        redacted["client_secret"] = REDACTED
    return redacted


def redact_amqp(amqp: dict[str, Any] | None) -> dict[str, Any] | None:
    """Redact embedded credentials in the AMQP URL (e.g. amqp://user:pass@…)."""
    if not amqp:
        return amqp
    redacted = dict(amqp)
    url = redacted.get("url") or ""
    # Strip any "user:pass@" segment from the URL while keeping host/port/path.
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        creds, _, host = rest.partition("@")
        if ":" in creds:
            user, _ = creds.split(":", 1)
            redacted["url"] = f"{scheme}://{user}:{REDACTED}@{host}"
    return redacted


def strip_redacted(key: str, new_value: Any, existing_value: Any) -> Any:
    """Drop redaction sentinels from ``new_value`` so a round-trip GET→PUT
    never overwrites the on-disk secret with the placeholder.

    Specifically:
    - ``flight_blender.auth.client_secret`` / ``opensky.auth.client_secret``
      that equal the redaction sentinel are replaced with the existing
      on-disk value (or dropped if no prior value exists).
    - ``amqp.url`` containing the redaction sentinel as the password is
      replaced with the existing on-disk URL.
    """
    if new_value is None or not isinstance(new_value, dict):
        return new_value
    cleaned = dict(new_value)
    if key in ("flight_blender", "opensky"):
        auth = cleaned.get("auth")
        if isinstance(auth, dict) and auth.get("client_secret") == REDACTED:
            existing_secret = ""
            if isinstance(existing_value, dict):
                existing_auth = existing_value.get("auth") or {}
                existing_secret = existing_auth.get("client_secret", "")
            auth["client_secret"] = existing_secret
            cleaned["auth"] = auth
    elif key == "amqp":
        url = cleaned.get("url") or ""
        if REDACTED in url and isinstance(existing_value, dict):
            cleaned["url"] = existing_value.get("url", url)
    return cleaned
