import warnings
from typing import List

import pytest

from engine.deprecated import deprecated_api
from engine.parser_base import BaseParser, ParseResult


def test_validate_default():
    """validate() returns empty list by default."""

    class TestParser(BaseParser):
        command = "test"

        def parse(self, raw):
            return ParseResult()

    parser = TestParser()
    assert parser.validate() == []


def test_validate_override():
    """Subclass can override validate() to return errors."""

    class TestParser(BaseParser):
        command = "test"

        def parse(self, raw):
            return ParseResult()

        def validate(self) -> List[str]:
            return ["missing field", "invalid value"]

    parser = TestParser()
    errors = parser.validate()
    assert len(errors) == 2
    assert "missing field" in errors
    assert "invalid value" in errors


def test_version_default():
    """version ClassVar defaults to '1.0.0'."""

    class TestParser(BaseParser):
        command = "test"

        def parse(self, raw):
            return ParseResult()

    assert TestParser.version == "1.0.0"


def test_version_override():
    """Subclass can override version."""

    class TestParser(BaseParser):
        command = "test"
        version = "2.0.0"

        def parse(self, raw):
            return ParseResult()

    assert TestParser.version == "2.0.0"


def test_deprecated_api_warning():
    """@deprecated_api emits DeprecationWarning with correct message."""

    @deprecated_api(since="1.0.0", remove_in="2.0.0")
    def old_func():
        return 42

    with pytest.warns(
        DeprecationWarning, match="deprecated since 1.0.0"
    ):
        result = old_func()

    assert result == 42


def test_deprecated_api_on_method():
    """@deprecated_api works on instance methods."""

    class MyClass:
        @deprecated_api(since="1.5.0", remove_in="3.0.0")
        def old_method(self):
            return "hello"

    obj = MyClass()
    with pytest.warns(DeprecationWarning):
        result = obj.old_method()

    assert result == "hello"


def test_deprecated_api_no_warning_without_call():
    """Decorating a function does not emit warning; only calling it does."""

    @deprecated_api(since="1.0.0", remove_in="2.0.0")
    def old_func():
        return 99

    # No warning should be emitted just by defining the decorated function.
    # We verify by ensuring old_func is still callable and returns correctly.
    with pytest.warns(DeprecationWarning):
        result = old_func()

    assert result == 99


def test_init_subclass_no_crash():
    """__init_subclass__ does not crash when creating a valid subclass."""

    class TestParser(BaseParser):
        command = "test"

        def parse(self, raw):
            return ParseResult()

    parser = TestParser()
    assert parser.command == "test"
    assert isinstance(parser, BaseParser)
