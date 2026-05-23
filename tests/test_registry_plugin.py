"""Tests for PluginAwareParserRegistry — old/new style parser integration."""

import sys
import pytest
from engine.plugin_base import PluginBase, PluginManifest
from engine.plugin_exceptions import PluginValidationError
from engine.parser_base import BaseParser, FieldDef, ParseResult
from engine.registry import PluginAwareParserRegistry, _wrap_plugin


# ── _wrap_plugin unit tests ──────────────────────────────────────────────


class TestWrapPlugin:
    """_wrap_plugin adapter function converts PluginBase → BaseParser."""

    def test_basic_adapter_creation(self):
        """Wrap a PluginBase into a BaseParser-compatible adapter."""

        class _P(PluginBase):
            manifest = PluginManifest(
                name="unit_test", version="1.0", author="tester",
                description="unit", plugin_type="parser",
            )
            command = "show unit"
            fields = [FieldDef(key="x", label="X", category="device")]

            def validate(self):
                return []

            def parse(self, raw):
                return ParseResult(rows=[{"x": raw.strip()}])

        adapter = _wrap_plugin(_P())

        assert adapter.command == "show unit"
        assert len(adapter.fields) == 1
        assert adapter.fields[0].key == "x"
        assert isinstance(adapter, BaseParser)

    def test_adapter_delegates_parse(self):
        """Adapter.parse() delegates to the wrapped plugin's parse()."""

        class _P(PluginBase):
            manifest = PluginManifest(
                name="delegate_test", version="1.0", author="t",
                description="delegate", plugin_type="parser",
            )
            command = "show delegate"
            fields = [FieldDef(key="k", label="K", category="device")]

            def validate(self):
                return []

            def parse(self, raw):
                return ParseResult(rows=[{"k": f"parsed:{raw}"}])

        adapter = _wrap_plugin(_P())
        result = adapter.parse("hello")
        assert result.rows[0]["k"] == "parsed:hello"

    def test_adapter_can_register_in_registry(self):
        """A wrapped plugin can be registered in ParserRegistry."""
        registry = PluginAwareParserRegistry()

        class _P(PluginBase):
            manifest = PluginManifest(
                name="reg_test", version="1.0", author="t",
                description="reg", plugin_type="parser",
            )
            command = "show reg_test"
            fields = [FieldDef(key="v", label="V", category="device")]

            def validate(self):
                return []

            def parse(self, raw):
                return ParseResult(rows=[{"v": raw.strip()}])

        adapter = _wrap_plugin(_P())
        registry.register_custom(adapter)

        assert registry.has("show reg_test")
        result = registry.parse("show reg_test", "data")
        assert result.rows[0]["v"] == "data"


# ── PluginAwareParserRegistry integration tests ─────────────────────────


def _setup_registry_test(parsers_dir, monkeypatch, module_name, code):
    """Write *code* into ``parsers_dir / module_name``, then
    monkeypatch ``parsers.__path__`` and clear previous imports so
    ``load_custom_parsers()`` picks up only the temporary module."""

    # Write the parser module file
    (parsers_dir / module_name).write_text(code)

    import parsers as parsers_pkg

    # Point parsers.__path__ to our temp directory only
    monkeypatch.setattr(parsers_pkg, "__path__", [str(parsers_dir)])

    # Clean up any previously imported module under parsers.<module_name>
    mod_key = f"parsers.{module_name.replace('.py', '')}"
    if mod_key in sys.modules:
        del sys.modules[mod_key]

    return parsers_pkg


OLD_STYLE_CODE = """\
from engine.parser_base import BaseParser, FieldDef, ParseResult

class ShowTempOld(BaseParser):
    command = "show temp-old"
    fields = [FieldDef(key="val", label="Value", category="device")]

    def parse(self, raw):
        return ParseResult(rows=[{"val": raw.strip()}])
"""

NEW_STYLE_CODE = """\
from engine.plugin_base import PluginBase, PluginManifest
from engine.parser_base import FieldDef, ParseResult
from typing import List

_mft = PluginManifest(
    name="temp_new",
    version="1.0",
    author="tester",
    description="A new-style plugin parser for testing",
    plugin_type="parser",
)

class TempNewPlugin(PluginBase):
    manifest = _mft
    command = "show temp-new"
    fields = [FieldDef(key="result", label="Result", category="device")]

    def validate(self) -> List[str]:
        return []

    def parse(self, raw):
        return ParseResult(rows=[{"result": raw.strip()}])
"""

INVALID_CODE = """\
from engine.plugin_base import PluginBase, PluginManifest
from engine.parser_base import FieldDef, ParseResult
from typing import List

_mft = PluginManifest(
    name="temp_invalid",
    version="0.1",
    author="bad",
    description="An invalid parser plugin",
    plugin_type="parser",
)

class TempInvalidPlugin(PluginBase):
    manifest = _mft
    command = "show temp-invalid"
    fields = []

    def validate(self) -> List[str]:
        return ["missing required fields: no fields defined"]

    def parse(self, raw):
        return ParseResult()
"""


class TestOldStyleAutoManifest:
    """Old-style parsers (BaseParser, no PluginBase) still load correctly."""

    def test_old_style_registers_and_parses(self, parsers_tmpdir, monkeypatch):
        _setup_registry_test(
            parsers_tmpdir, monkeypatch, "test_old_parser.py", OLD_STYLE_CODE,
        )
        registry = PluginAwareParserRegistry()
        registry.load_custom_parsers()

        assert registry.has("show temp-old"), "Old-style parser should be registered"
        result = registry.parse("show temp-old", "hello-old")
        assert result is not None
        assert result.rows[0]["val"] == "hello-old"
        assert len(registry.get_load_errors()) == 0


class TestNewStylePluginParser:
    """New-style PluginBase parsers discovered and registered via PluginManager."""

    def test_new_style_discovers_and_registers(self, parsers_tmpdir, monkeypatch):
        _setup_registry_test(
            parsers_tmpdir, monkeypatch, "test_new_plugin.py", NEW_STYLE_CODE,
        )
        registry = PluginAwareParserRegistry()
        registry.load_custom_parsers()

        assert registry.has("show temp-new"), "New-style parser should be registered"
        result = registry.parse("show temp-new", "hello-new")
        assert result is not None
        assert result.rows[0]["result"] == "hello-new"

    def test_validation_failure_not_registered(self, parsers_tmpdir, monkeypatch):
        _setup_registry_test(
            parsers_tmpdir, monkeypatch, "test_bad_plugin.py", INVALID_CODE,
        )
        registry = PluginAwareParserRegistry()
        registry.load_custom_parsers()

        # The invalid parser should NOT be in the registry
        assert not registry.has("show temp-invalid"), (
            "Validation-failing parser should NOT be registered"
        )

        # It SHOULD appear in load errors
        errors = registry.get_load_errors()
        assert len(errors) >= 1
        assert any("temp_invalid" in e for e in errors), (
            f"Expected error mentioning 'temp_invalid' in {errors}"
        )

    def test_get_load_errors_contains_validation_failures(self, parsers_tmpdir, monkeypatch):
        """Verifies get_load_errors() returns validation failure messages."""
        _setup_registry_test(
            parsers_tmpdir, monkeypatch, "test_invalid.py", INVALID_CODE,
        )
        registry = PluginAwareParserRegistry()
        registry.load_custom_parsers()

        errors = registry.get_load_errors()
        assert len(errors) >= 1
        msg = errors[0]
        assert "temp_invalid" in msg
        assert "missing required fields" in msg

    def test_new_style_parser_validate_called(self, parsers_tmpdir, monkeypatch):
        """PluginBase.validate() is called during discovery."""
        _setup_registry_test(
            parsers_tmpdir, monkeypatch, "test_new_valid.py", NEW_STYLE_CODE,
        )
        registry = PluginAwareParserRegistry()
        registry.load_custom_parsers()

        # No errors means validate() passed
        assert registry.has("show temp-new")
        assert not any("temp_new" in e for e in registry.get_load_errors())


class TestBothStylesCoexist:
    """Old and new style parsers can coexist in the same registry."""

    def test_mixed_modules_both_loaded(self, parsers_tmpdir, monkeypatch):
        """Two modules — one old style, one new — both registered."""
        _setup_registry_test(
            parsers_tmpdir, monkeypatch, "p_old.py", OLD_STYLE_CODE,
        )
        # Also write a new-style module
        (parsers_tmpdir / "p_new.py").write_text(NEW_STYLE_CODE)
        import parsers as parsers_pkg
        monkeypatch.setattr(parsers_pkg, "__path__", [str(parsers_tmpdir)])
        # Clean cache
        for k in list(sys.modules):
            if k.startswith("parsers.") and "p_" in k:
                del sys.modules[k]

        registry = PluginAwareParserRegistry()
        registry.load_custom_parsers()

        assert registry.has("show temp-old")
        assert registry.has("show temp-new")
        assert len(registry._custom_parsers) == 2


class TestActualParsersStillWork:
    """Regression: the real 11 parsers/*.py still load via PluginAwareRegistry."""

    def test_real_old_style_parsers_loaded(self):
        """Actual parsers directory old-style parsers load with zero errors."""
        registry = PluginAwareParserRegistry()
        registry.load_custom_parsers()

        # Spot-check a few well-known old-style parsers
        for cmd in ["show clock", "show version", "show logging"]:
            assert registry.has(cmd), f"Old-style parser '{cmd}' should be registered"

        assert len(registry._custom_parsers) >= 11, (
            f"Expected ≥11 parsers, got {len(registry._custom_parsers)}"
        )
        # The actual parsers should have no errors (they are all valid)
        assert len(registry.get_load_errors()) == 0, (
            f"Unexpected load errors: {registry.get_load_errors()}"
        )
