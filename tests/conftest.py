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


# ── Topology test fixtures ────────────────────────────────────────────

@pytest.fixture
def topo_config():
    from engine.topology import TopologyConfig
    return TopologyConfig()


@pytest.fixture
def empty_parsed_data():
    return {}


@pytest.fixture
def single_device_data():
    return {
        "device": [
            {"_device_name": "CORE-SW-01", "_device_ip": "10.0.0.1",
             "model": "Cisco 3850"},
        ],
        "neighbor": [],
    }


@pytest.fixture
def bidirectional_data():
    return {
        "device": [
            {"_device_name": "CORE-SW-01", "_device_ip": "10.0.0.1",
             "model": "Cisco 3850"},
            {"_device_name": "CORE-SW-02", "_device_ip": "10.0.0.2",
             "model": "Cisco 3850"},
        ],
        "neighbor": [
            {"_device_name": "CORE-SW-01", "_device_ip": "10.0.0.1",
             "neighbor_name": "CORE-SW-02", "neighbor_ip": "10.0.0.2",
             "interface": "Gi0/1", "neighbor_interface": "Gi0/1",
             "neighbor_model": "Cisco 3850"},
            {"_device_name": "CORE-SW-02", "_device_ip": "10.0.0.2",
             "neighbor_name": "CORE-SW-01", "neighbor_ip": "10.0.0.1",
             "interface": "Gi0/1", "neighbor_interface": "Gi0/1",
             "neighbor_model": "Cisco 3850"},
        ],
    }


@pytest.fixture
def multiport_data():
    return {
        "device": [
            {"_device_name": "CORE-SW-01", "_device_ip": "10.0.0.1",
             "model": "Cisco 3850"},
            {"_device_name": "HX-SW-Floor1", "_device_ip": "10.0.1.1",
             "model": "Cisco 9300"},
        ],
        "neighbor": [
            {"_device_name": "CORE-SW-01", "_device_ip": "10.0.0.1",
             "neighbor_name": "HX-SW-Floor1", "neighbor_ip": "10.0.1.1",
             "interface": "Gi0/1", "neighbor_interface": "Gi0/1"},
            {"_device_name": "CORE-SW-01", "_device_ip": "10.0.0.1",
             "neighbor_name": "HX-SW-Floor1", "neighbor_ip": "10.0.1.1",
             "interface": "Gi0/2", "neighbor_interface": "Gi0/2"},
            {"_device_name": "CORE-SW-01", "_device_ip": "10.0.0.1",
             "neighbor_name": "HX-SW-Floor1", "neighbor_ip": "10.0.1.1",
             "interface": "Gi0/3", "neighbor_interface": "Gi0/3"},
        ],
    }


@pytest.fixture
def external_device_data():
    return {
        "device": [
            {"_device_name": "CORE-SW-01", "_device_ip": "10.0.0.1",
             "model": "Cisco 3850"},
        ],
        "neighbor": [
            {"_device_name": "CORE-SW-01", "_device_ip": "10.0.0.1",
             "neighbor_name": "external-router", "neighbor_ip": "8.8.8.8",
             "interface": "Gi0/0", "neighbor_interface": "Gi0/0",
             "neighbor_model": "Unknown"},
        ],
    }


@pytest.fixture
def terminal_device_data():
    return {
        "device": [
            {"_device_name": "ACC-SW-B1", "_device_ip": "10.0.10.1",
             "model": "Cisco 2960"},
        ],
        "neighbor": [
            {"_device_name": "ACC-SW-B1", "_device_ip": "10.0.10.1",
             "neighbor_name": "PC-001", "neighbor_ip": "10.0.99.99",
             "interface": "Gi0/2", "neighbor_interface": ""},
        ],
    }


@pytest.fixture
def building_test_data():
    return {
        "device": [
            {"_device_name": "MZ-SW-01", "_device_ip": "10.0.0.1",
             "model": "Cisco 3850"},
            {"_device_name": "ZY-SW-02", "_device_ip": "10.0.0.2",
             "model": "Cisco 3850"},
            {"_device_name": "NoMatch-SW", "_device_ip": "10.0.0.3",
             "model": "Cisco 2960"},
        ],
        "neighbor": [],
    }


@pytest.fixture
def full_integration_data():
    return {
        "device": [
            {"_device_name": "CORE-SW-01", "_device_ip": "10.0.0.1",
             "model": "Cisco 3850-48T"},
            {"_device_name": "CORE-SW-02", "_device_ip": "10.0.0.2",
             "model": "Cisco 3850-48T"},
            {"_device_name": "HX-SW-Floor1", "_device_ip": "10.0.1.1",
             "model": "Cisco 9300-48P"},
            {"_device_name": "ACC-SW-B1", "_device_ip": "10.0.10.1",
             "model": "Cisco 2960X-48"},
            {"_device_name": "ACC-SW-B2", "_device_ip": "10.0.10.2",
             "model": "Cisco 2960X-48"},
        ],
        "neighbor": [
            {"_device_name": "CORE-SW-01", "_device_ip": "10.0.0.1",
             "neighbor_name": "CORE-SW-02", "neighbor_ip": "10.0.0.2",
             "interface": "Gi0/1", "neighbor_interface": "Gi0/1"},
            {"_device_name": "CORE-SW-01", "_device_ip": "10.0.0.1",
             "neighbor_name": "HX-SW-Floor1", "neighbor_ip": "10.0.1.1",
             "interface": "Gi0/2", "neighbor_interface": "Gi0/48"},
            {"_device_name": "CORE-SW-02", "_device_ip": "10.0.0.2",
             "neighbor_name": "CORE-SW-01", "neighbor_ip": "10.0.0.1",
             "interface": "Gi0/1", "neighbor_interface": "Gi0/1"},
            {"_device_name": "HX-SW-Floor1", "_device_ip": "10.0.1.1",
             "neighbor_name": "CORE-SW-01", "neighbor_ip": "10.0.0.1",
             "interface": "Gi0/48", "neighbor_interface": "Gi0/2"},
            {"_device_name": "HX-SW-Floor1", "_device_ip": "10.0.1.1",
             "neighbor_name": "ACC-SW-B1", "neighbor_ip": "10.0.10.1",
             "interface": "Gi0/1", "neighbor_interface": "Gi0/48"},
            {"_device_name": "HX-SW-Floor1", "_device_ip": "10.0.1.1",
             "neighbor_name": "ACC-SW-B2", "neighbor_ip": "10.0.10.2",
             "interface": "Gi0/2", "neighbor_interface": "Gi0/48"},
            {"_device_name": "ACC-SW-B1", "_device_ip": "10.0.10.1",
             "neighbor_name": "HX-SW-Floor1", "neighbor_ip": "10.0.1.1",
             "interface": "Gi0/48", "neighbor_interface": "Gi0/1"},
            {"_device_name": "ACC-SW-B1", "_device_ip": "10.0.10.1",
             "neighbor_name": "ACC-SW-B2", "neighbor_ip": "10.0.10.2",
             "interface": "Gi0/1", "neighbor_interface": "Gi0/2"},
            {"_device_name": "ACC-SW-B2", "_device_ip": "10.0.10.2",
             "neighbor_name": "HX-SW-Floor1", "neighbor_ip": "10.0.1.1",
             "interface": "Gi0/48", "neighbor_interface": "Gi0/2"},
            {"_device_name": "ACC-SW-B2", "_device_ip": "10.0.10.2",
             "neighbor_name": "ACC-SW-B1", "neighbor_ip": "10.0.10.1",
             "interface": "Gi0/2", "neighbor_interface": "Gi0/1"},
        ],
    }
