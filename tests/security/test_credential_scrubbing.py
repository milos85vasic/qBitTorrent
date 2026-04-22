"""
Security tests for credential scrubbing in log output.

Verifies that a logging.Filter redacts sensitive values
(PASSWORD, COOKIE, TOKEN, SECRET, API_KEY) from log records.
"""

import logging
import os
import sys

import pytest

_src = os.path.join(os.path.dirname(__file__), "..", "..", "download-proxy", "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from config.log_filter import CredentialScrubber  # noqa: E402


class TestCredentialScrubbing:
    """Log filter must redact credential-like patterns."""

    def _make_record(self, msg: str) -> logging.LogRecord:
        return logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=None,
            exc_info=None,
        )

    def test_password_scrubbed(self):
        scrubber = CredentialScrubber()
        record = self._make_record("Login with PASSWORD=secret123 failed")
        scrubber.filter(record)
        assert "secret123" not in record.getMessage()
        assert "PASSWORD=***" in record.getMessage()

    def test_token_scrubbed(self):
        scrubber = CredentialScrubber()
        record = self._make_record("Using TOKEN=abc123def")
        scrubber.filter(record)
        assert "abc123def" not in record.getMessage()
        assert "TOKEN=***" in record.getMessage()

    def test_cookie_scrubbed(self):
        scrubber = CredentialScrubber()
        record = self._make_record("Request COOKIE=sessionid_xyz")
        scrubber.filter(record)
        assert "sessionid_xyz" not in record.getMessage()
        assert "COOKIE=***" in record.getMessage()

    def test_secret_scrubbed(self):
        scrubber = CredentialScrubber()
        record = self._make_record("Loaded SECRET=hunter2")
        scrubber.filter(record)
        assert "hunter2" not in record.getMessage()
        assert "SECRET=***" in record.getMessage()

    def test_api_key_scrubbed(self):
        scrubber = CredentialScrubber()
        record = self._make_record("Configured API_KEY=sk_live_12345")
        scrubber.filter(record)
        assert "sk_live_12345" not in record.getMessage()
        assert "API_KEY=***" in record.getMessage()

    def test_normal_message_unchanged(self):
        scrubber = CredentialScrubber()
        original = "Search completed with 42 results"
        record = self._make_record(original)
        scrubber.filter(record)
        assert record.getMessage() == original

    def test_mixed_credentials_and_normal_text(self):
        scrubber = CredentialScrubber()
        record = self._make_record("User admin logged in with PASSWORD=s3cret, status ok")
        scrubber.filter(record)
        assert "s3cret" not in record.getMessage()
        assert "PASSWORD=***" in record.getMessage()
        assert "User admin logged in" in record.getMessage()
        assert "status ok" in record.getMessage()

    def test_multiple_credentials_in_one_message(self):
        scrubber = CredentialScrubber()
        record = self._make_record("TOKEN=abc and PASSWORD=xyz in one line")
        scrubber.filter(record)
        assert "abc" not in record.getMessage()
        assert "xyz" not in record.getMessage()
        assert "TOKEN=***" in record.getMessage()
        assert "PASSWORD=***" in record.getMessage()

    def test_case_insensitive_matching(self):
        scrubber = CredentialScrubber()
        record = self._make_record("Using password=lowercase and TOKEN=uppercase")
        scrubber.filter(record)
        assert "lowercase" not in record.getMessage()
        assert "uppercase" not in record.getMessage()

    def test_colon_separator_scrubbed(self):
        scrubber = CredentialScrubber()
        record = self._make_record("Header: PASSWORD:mysecretpass")
        scrubber.filter(record)
        assert "mysecretpass" not in record.getMessage()
        assert "PASSWORD:***" in record.getMessage()

    def test_filter_returns_true(self):
        scrubber = CredentialScrubber()
        record = self._make_record("anything")
        assert scrubber.filter(record) is True
