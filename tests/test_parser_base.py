import pytest
from engine.parser_base import BaseParser, ParseResult, FieldDef


def test_base_parser_cannot_instantiate():
    """BaseParser is abstract and cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseParser()


def test_valid_subclass_can_instantiate(mock_parser):
    """A concrete subclass of BaseParser can be instantiated."""
    assert mock_parser is not None
    assert isinstance(mock_parser, BaseParser)


def test_parse_returns_parseresult(mock_parser):
    """parse() returns a ParseResult instance."""
    result = mock_parser.parse('')
    assert isinstance(result, ParseResult)


def test_parseresult_has_rows(mock_parser):
    """ParseResult has a rows attribute containing parsed data."""
    result = mock_parser.parse('')
    assert hasattr(result, 'rows')
    assert isinstance(result.rows, list)
    assert len(result.rows) == 1
    assert result.rows[0]['interface'] == 'Gi0/1'


def test_command_class_attribute(mock_parser):
    """Subclasses have an accessible command class attribute."""
    assert mock_parser.command == 'test command'


def test_fields_class_attribute(mock_parser):
    """Subclasses have an accessible fields class attribute."""
    assert len(mock_parser.fields) == 1
    field = mock_parser.fields[0]
    assert isinstance(field, FieldDef)
    assert field.key == 'interface'
    assert field.label == '接口'
    assert field.category == 'interface'
    assert field.join_group == 'interface'
    assert field.join_key == 'normalized_iface'
