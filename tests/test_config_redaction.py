"""Unit tests for openutm_verification.server.config_redaction."""

from openutm_verification.server.config_redaction import (
    REDACTED,
    redact_amqp,
    redact_auth,
    strip_redacted,
)


class TestRedactAuth:
    def test_redacts_client_secret_when_present(self):
        result = redact_auth({"client_id": "id", "client_secret": "supersecret"})
        assert result["client_secret"] == REDACTED
        assert result["client_id"] == "id"

    def test_leaves_empty_secret_alone(self):
        result = redact_auth({"client_id": "id", "client_secret": ""})
        assert result["client_secret"] == ""

    def test_handles_missing_secret(self):
        result = redact_auth({"client_id": "id"})
        assert "client_secret" not in result

    def test_does_not_mutate_input(self):
        original = {"client_secret": "supersecret"}
        redact_auth(original)
        assert original["client_secret"] == "supersecret"


class TestRedactAmqp:
    def test_returns_none_for_none(self):
        assert redact_amqp(None) is None

    def test_returns_falsy_unchanged(self):
        assert redact_amqp({}) == {}

    def test_redacts_password_in_url(self):
        result = redact_amqp({"url": "amqp://user:pass@host:5672/vhost"})
        assert result["url"] == f"amqp://user:{REDACTED}@host:5672/vhost"

    def test_preserves_url_without_credentials(self):
        result = redact_amqp({"url": "amqp://host:5672/"})
        assert result["url"] == "amqp://host:5672/"

    def test_preserves_url_with_user_only(self):
        # No colon in creds = no password to redact.
        result = redact_amqp({"url": "amqp://user@host:5672/"})
        assert result["url"] == "amqp://user@host:5672/"

    def test_handles_empty_url(self):
        result = redact_amqp({"url": ""})
        assert result["url"] == ""

    def test_does_not_mutate_input(self):
        original = {"url": "amqp://user:pass@host"}
        redact_amqp(original)
        assert original["url"] == "amqp://user:pass@host"


class TestStripRedacted:
    def test_returns_none_passthrough(self):
        assert strip_redacted("flight_blender", None, {"auth": {"client_secret": "x"}}) is None

    def test_returns_non_dict_passthrough(self):
        assert strip_redacted("flight_blender", "not-a-dict", {}) == "not-a-dict"

    def test_replaces_redacted_secret_with_existing(self):
        new = {"auth": {"client_secret": REDACTED, "client_id": "id"}}
        existing = {"auth": {"client_secret": "real-secret"}}
        result = strip_redacted("flight_blender", new, existing)
        assert result["auth"]["client_secret"] == "real-secret"

    def test_replaces_redacted_secret_with_empty_when_no_prior(self):
        new = {"auth": {"client_secret": REDACTED}}
        result = strip_redacted("flight_blender", new, None)
        assert result["auth"]["client_secret"] == ""

    def test_keeps_real_new_secret(self):
        new = {"auth": {"client_secret": "new-secret"}}
        existing = {"auth": {"client_secret": "old-secret"}}
        result = strip_redacted("opensky", new, existing)
        assert result["auth"]["client_secret"] == "new-secret"

    def test_amqp_url_with_redacted_password_falls_back_to_existing(self):
        new = {"url": f"amqp://user:{REDACTED}@host:5672/"}
        existing = {"url": "amqp://user:realpw@host:5672/"}
        result = strip_redacted("amqp", new, existing)
        assert result["url"] == "amqp://user:realpw@host:5672/"

    def test_amqp_url_without_redaction_unchanged(self):
        new = {"url": "amqp://user:newpw@host:5672/"}
        existing = {"url": "amqp://user:oldpw@host:5672/"}
        result = strip_redacted("amqp", new, existing)
        assert result["url"] == "amqp://user:newpw@host:5672/"

    def test_amqp_redacted_url_with_no_existing_keeps_value(self):
        new = {"url": f"amqp://user:{REDACTED}@host"}
        result = strip_redacted("amqp", new, None)
        # No existing dict to fall back on, so the (still-redacted) URL is
        # left as-is. Validation downstream will reject it.
        assert result["url"] == f"amqp://user:{REDACTED}@host"

    def test_unknown_key_passes_through(self):
        new = {"foo": "bar", "auth": {"client_secret": REDACTED}}
        result = strip_redacted("data_files", new, {})
        assert result == new
