import pytest
from engine.parser_base import BaseParser, ParseResult, FieldDef


@pytest.fixture
def sample_parsed_data():
    return {
        'device': [{'device_ip': '10.0.0.1', 'device_name': 'sw1', 'system_software_version': '10.4(3)'}],
        'interface': [{'interface': 'Gi0/1', 'status': 'up', 'vlan': '100'}],
    }


@pytest.fixture
def mock_parser():
    class TestParser(BaseParser):
        command = 'test command'
        fields = [FieldDef(key='interface', label='接口', category='interface', join_group='interface', join_key='normalized_iface')]

        def parse(self, raw):
            return ParseResult(rows=[{'interface': 'Gi0/1', 'status': 'up'}])

    return TestParser()


@pytest.fixture
def parsers_tmpdir(tmp_path):
    """Create an isolated parsers package directory for tests.

    Returns (tmp_parsers_dir, monkeypatch_ctx) — caller must use
    monkeypatch to redirect parsers.__path__ and clean sys.modules.
    """
    d = tmp_path / "parsers"
    d.mkdir()
    (d / "__init__.py").write_text("# test parsers package")
    return d
