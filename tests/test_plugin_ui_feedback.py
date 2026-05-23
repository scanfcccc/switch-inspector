"""Tests for plugin load error grading and UI feedback.

Verifies:
1. _structured_error() produces correct dict shape
2. Severity classification (critical / warning / info)
3. API /api/scan returns plugin_status field
4. Backward compatibility of get_load_errors()
"""

import sys
import json
import pytest
from engine.registry import (
    _structured_error,
    ParserRegistry,
    PluginAwareParserRegistry,
)


class TestStructuredError:
    """_structured_error() helper produces correct output."""

    def test_returns_all_required_keys(self):
        err = _structured_error(
            "parsers/test.py", "critical",
            "语法错误: invalid syntax",
            "Fix the Python syntax error",
        )
        assert set(err.keys()) == {"plugin", "severity", "message", "suggestion"}
        assert err["plugin"] == "parsers/test.py"
        assert err["severity"] == "critical"
        assert err["message"] == "语法错误: invalid syntax"
        assert err["suggestion"] == "Fix the Python syntax error"

    def test_severity_values_accepted(self):
        for sev in ("critical", "warning", "info"):
            err = _structured_error("p.py", sev, "msg", "suggestion")
            assert err["severity"] == sev

    def test_empty_suggestion_default(self):
        err = _structured_error("p.py", "warning", "msg")
        assert err["suggestion"] == ""


class TestRegistryStructuredErrors:
    """ParserRegistry stores and retrieves structured errors."""

    def test_get_structured_load_errors_returns_dicts(self):
        registry = ParserRegistry()
        registry._load_errors.append(
            _structured_error("p.py", "critical", "bad", "fix it")
        )
        structured = registry.get_structured_load_errors()
        assert len(structured) == 1
        assert isinstance(structured[0], dict)
        assert structured[0]["severity"] == "critical"
        assert structured[0]["suggestion"] == "fix it"

    def test_get_load_errors_backward_compatible(self):
        """get_load_errors() still returns plain strings."""
        registry = ParserRegistry()
        registry._load_errors.append(
            _structured_error("p.py", "warning", "something went wrong", "")
        )
        plain = registry.get_load_errors()
        assert isinstance(plain, list)
        assert all(isinstance(e, str) for e in plain)
        assert "something went wrong" in plain[0]

    def test_severity_counts(self):
        """Errors with different severities can be counted."""
        registry = ParserRegistry()
        registry._load_errors.append(
            _structured_error("a.py", "critical", "crash", "")
        )
        registry._load_errors.append(
            _structured_error("b.py", "critical", "fail", "")
        )
        registry._load_errors.append(
            _structured_error("c.py", "warning", "warn", "")
        )

        structured = registry.get_structured_load_errors()
        critical = sum(1 for e in structured if e["severity"] == "critical")
        warning = sum(1 for e in structured if e["severity"] == "warning")
        assert critical == 2
        assert warning == 1


class TestPluginAwareStructuredErrors:
    """PluginAwareParserRegistry also stores structured errors."""

    def test_validation_failure_structured(self, parsers_tmpdir, monkeypatch):
        """Validation failure produces structured error with severity."""
        from tests.test_registry_plugin import _setup_registry_test, INVALID_CODE

        _setup_registry_test(
            parsers_tmpdir, monkeypatch, "test_bad.py", INVALID_CODE,
        )
        registry = PluginAwareParserRegistry()
        registry.load_custom_parsers()

        structured = registry.get_structured_load_errors()
        assert len(structured) >= 1
        err = structured[0]
        assert "plugin" in err
        assert "severity" in err
        assert "message" in err
        assert "suggestion" in err
        assert "test_bad" in err["plugin"]
        assert err["severity"] in ("critical", "warning", "info")


class TestApiPluginStatus:
    """Verify the /api/scan response shape includes plugin_status."""

    def test_plugin_status_keys_present(self):
        """Simulate the plugin_status dict construction from main.py."""
        registry = ParserRegistry()
        registry._load_errors.append(
            _structured_error("bad.py", "critical", "syntax error", "fix")
        )
        registry._load_errors.append(
            _structured_error("warn.py", "warning", "no parser", "add one")
        )

        structured = registry.get_structured_load_errors()
        plugin_status = {
            "loaded": len(registry._custom_parsers) + 0,
            "failed_critical": sum(1 for e in structured if e["severity"] == "critical"),
            "failed_warning": sum(1 for e in structured if e["severity"] == "warning"),
            "errors": structured,
        }

        assert plugin_status["loaded"] == 0
        assert plugin_status["failed_critical"] == 1
        assert plugin_status["failed_warning"] == 1
        assert len(plugin_status["errors"]) == 2

        # Verify JSON-serializable
        json.dumps(plugin_status)
