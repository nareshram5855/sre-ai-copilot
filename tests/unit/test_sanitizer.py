"""Unit tests for the data sanitizer — the compliance-critical component."""
import pytest
from backend.llm.sanitizer import sanitize, _scrub


class TestScrub:

    def test_internal_hostname_redacted(self):
        assert "[INTERNAL_HOST]" in _scrub("host ping-identity.internal failed")

    def test_corp_domain_redacted(self):
        assert "[INTERNAL_HOST]" in _scrub("server db01.corp is down")

    def test_rfc1918_10_block_redacted(self):
        assert "[PRIVATE_IP]" in _scrub("connecting to 10.0.1.23:5432")

    def test_rfc1918_192168_block_redacted(self):
        assert "[PRIVATE_IP]" in _scrub("host 192.168.1.100 unreachable")

    def test_rfc1918_172_block_redacted(self):
        assert "[PRIVATE_IP]" in _scrub("172.16.0.5 timed out")

    def test_password_credential_redacted(self):
        result = _scrub("password=supersecret123")
        assert "supersecret123" not in result
        assert "[REDACTED]" in result

    def test_token_credential_redacted(self):
        result = _scrub("token=eyJhbGciOiJSUzI1")
        assert "eyJhbGciOiJSUzI1" not in result

    def test_aws_arn_redacted(self):
        result = _scrub("arn:aws:iam::123456789012:role/my-role")
        assert "123456789012" not in result

    def test_public_hostname_not_redacted(self):
        result = _scrub("connecting to api.github.com")
        assert "api.github.com" in result

    def test_public_ip_not_redacted(self):
        result = _scrub("8.8.8.8 is reachable")
        assert "8.8.8.8" in result

    def test_empty_string(self):
        assert _scrub("") == ""


class TestSanitize:

    def test_returns_deep_copy(self):
        payload = {"name": "alert", "description": "10.0.1.1 failed", "labels": {}}
        result = sanitize(payload)
        assert payload["description"] == "10.0.1.1 failed"  # original unchanged
        assert "[PRIVATE_IP]" in result["description"]

    def test_name_field_sanitized(self):
        payload = {"name": "alert on db.internal", "description": "", "labels": {}}
        assert "[INTERNAL_HOST]" in sanitize(payload)["name"]

    def test_labels_values_sanitized(self):
        payload = {"name": "alert", "description": "", "labels": {"host": "db.internal"}}
        assert "[INTERNAL_HOST]" in sanitize(payload)["labels"]["host"]

    def test_labels_keys_preserved(self):
        payload = {"name": "a", "description": "", "labels": {"namespace": "iam"}}
        assert "namespace" in sanitize(payload)["labels"]

    def test_unknown_fields_preserved(self):
        payload = {"name": "a", "description": "", "labels": {}, "environment": "production"}
        assert sanitize(payload)["environment"] == "production"

    def test_multiple_ips_all_redacted(self):
        payload = {"name": "a", "description": "10.0.1.1 and 192.168.1.5 failing", "labels": {}}
        result = sanitize(payload)["description"]
        assert "10.0.1.1" not in result
        assert "192.168.1.5" not in result
        assert result.count("[PRIVATE_IP]") == 2
