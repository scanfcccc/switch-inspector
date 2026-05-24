import pytest
from engine.topology import (
    build_topology,
    TopologyConfig,
    TopologyNode,
    TopologyEdge,
    TopologyResult,
    TopologySummary,
    default_config,
    _detect_tier,
    _map_building,
    _strip_domain,
    _get_edge_type,
)


# ── Internal helpers ──────────────────────────────────────────────────

class TestInternalHelpers:

    def test_strip_domain(self):
        assert _strip_domain("CORE-SW-01.domain.com") == "CORE-SW-01"
        assert _strip_domain("CORE-SW-01") == "CORE-SW-01"
        assert _strip_domain("") == ""

    def test_detect_tier_from_name(self, topo_config):
        assert _detect_tier("CORE-SW-01", "", topo_config) == "core"
        assert _detect_tier("HX-SW-Floor2", "", topo_config) == "agg"
        assert _detect_tier("ACC-SW-B1", "", topo_config) == "access"
        assert _detect_tier("UnknownDevice", "", topo_config) == "access"

    def test_detect_tier_ip_fallback(self, topo_config):
        assert _detect_tier("SomeDevice", "10.0.0.1", topo_config) == "core"
        assert _detect_tier("SomeDevice", "10.0.1.1", topo_config) == "agg"
        assert _detect_tier("SomeDevice", "10.0.50.1", topo_config) == "access"

    def test_map_building(self, topo_config):
        assert _map_building("MZ-SW-01", topo_config) == "\u95e8\u8bca\u697c"
        assert _map_building("ZY-SW-02", topo_config) == "\u4e2d\u533b\u697c"
        assert _map_building("UnknownDevice", topo_config) == "\u672a\u5206\u7c7b"

    def test_get_edge_type(self):
        assert _get_edge_type("core", "agg") == "uplink"
        assert _get_edge_type("core", "core") == "peer"
        assert _get_edge_type("access", "core") == "access"
        assert _get_edge_type("agg", "access") == "uplink"
        assert _get_edge_type("core", "terminal") == "uplink"
        assert _get_edge_type("terminal", "core") == "access"


# ── Build topology ────────────────────────────────────────────────────

class TestBuildTopology:

    def test_empty_data_returns_empty_result(self):
        result = build_topology({})
        assert result.nodes == []
        assert result.edges == []
        assert result.summary.total_nodes == 0
        assert result.summary.managed_devices == 0
        assert result.summary.external_nodes == 0
        assert result.summary.internal_links == 0
        assert result.summary.external_links == 0

        result2 = build_topology({"device": [], "neighbor": []})
        assert result2.nodes == []
        assert result2.edges == []

    def test_single_device_no_neighbors(self, single_device_data):
        result = build_topology(single_device_data)
        assert len(result.nodes) == 1
        assert len(result.edges) == 0
        assert result.summary.total_nodes == 1
        assert result.summary.managed_devices == 1
        assert result.summary.external_nodes == 0

        node = result.nodes[0]
        assert node.name == "CORE-SW-01"
        assert node.id == "10.0.0.1"
        assert node.tier == "core"
        assert node.device_type == "managed"
        assert node.group == "\u672a\u5206\u7c7b"

    def test_tier_detection_from_name_in_build(self, single_device_data):
        result = build_topology(single_device_data)
        assert result.nodes[0].tier == "core"

    def test_tier_detection_ip_fallback_in_build(self, topo_config):
        data = {
            "device": [
                {"_device_name": "some-switch", "_device_ip": "10.0.0.1"},
            ],
            "neighbor": [],
        }
        result = build_topology(data)
        assert result.nodes[0].tier == "core"

    def test_link_deduplication_bidirectional(self, bidirectional_data):
        result = build_topology(bidirectional_data)
        assert len(result.nodes) == 2
        assert len(result.edges) == 1

        edge = result.edges[0]
        assert edge.count == 2
        assert edge.type == "peer"
        assert len(edge.links) == 2

        assert result.summary.total_nodes == 2
        assert result.summary.managed_devices == 2
        assert result.summary.internal_links == 1

    def test_link_bundling_multiport(self, multiport_data):
        result = build_topology(multiport_data)
        assert len(result.nodes) == 2
        assert len(result.edges) == 1

        edge = result.edges[0]
        assert edge.count == 3
        assert len(edge.links) == 3
        assert edge.type == "uplink"

    def test_external_device_detection(self, external_device_data):
        # Use show_terminals=True so external leaf nodes survive terminal filtering
        result = build_topology(external_device_data, show_terminals=True)
        assert len(result.nodes) == 2

        ext = next(n for n in result.nodes if n.device_type == "external")
        assert ext.id == "8.8.8.8"
        assert ext.name == "external-router"
        assert ext.device_type == "external"

        managed = next(n for n in result.nodes if n.device_type == "managed")
        assert managed.name == "CORE-SW-01"

        assert result.summary.total_nodes == 2
        assert result.summary.managed_devices == 1
        assert result.summary.external_nodes == 1
        assert result.summary.internal_links == 0
        assert result.summary.external_links == 1

    def test_terminal_filtering_default_hides_terminals(self, terminal_device_data):
        result = build_topology(terminal_device_data, show_terminals=False)
        assert len(result.nodes) == 1
        assert result.nodes[0].device_type == "managed"
        assert result.nodes[0].name == "ACC-SW-B1"
        assert result.summary.total_nodes == 1
        assert result.summary.managed_devices == 1
        assert result.summary.external_nodes == 0

    def test_terminal_filtering_show_terminals(self, terminal_device_data):
        result = build_topology(terminal_device_data, show_terminals=True)
        assert len(result.nodes) == 2

        terminal = next(n for n in result.nodes if n.tier == "terminal")
        assert terminal.name == "PC-001"
        assert terminal.id == "10.0.99.99"
        assert terminal.device_type == "external"

        managed = next(n for n in result.nodes if n.device_type == "managed")
        assert managed.name == "ACC-SW-B1"

        assert result.summary.total_nodes == 2
        assert result.summary.managed_devices == 1
        assert result.summary.external_nodes == 1

    def test_building_mapping_in_result(self, building_test_data):
        result = build_topology(building_test_data)
        assert len(result.nodes) == 3

        groups = {n.name: n.group for n in result.nodes}
        assert groups["MZ-SW-01"] == "\u95e8\u8bca\u697c"
        assert groups["ZY-SW-02"] == "\u4e2d\u533b\u697c"
        assert groups["NoMatch-SW"] == "\u672a\u5206\u7c7b"

    def test_full_integration_scenario(self, full_integration_data):
        result = build_topology(full_integration_data)

        assert len(result.nodes) == 5
        assert result.summary.total_nodes == 5
        assert result.summary.managed_devices == 5
        assert result.summary.external_nodes == 0

        by_name = {n.name: n for n in result.nodes}
        assert "CORE-SW-01" in by_name
        assert "CORE-SW-02" in by_name
        assert "HX-SW-Floor1" in by_name
        assert "ACC-SW-B1" in by_name
        assert "ACC-SW-B2" in by_name

        assert by_name["CORE-SW-01"].tier == "core"
        assert by_name["CORE-SW-02"].tier == "core"
        assert by_name["HX-SW-Floor1"].tier == "agg"
        assert by_name["ACC-SW-B1"].tier == "access"
        assert by_name["ACC-SW-B2"].tier == "access"

        assert len(result.edges) == 5
        assert result.summary.internal_links == 5
        assert result.summary.external_links == 0

        edge_types = {}
        for e in result.edges:
            edge_types[tuple(sorted([e.source, e.target]))] = e.type

        c1, c2 = "10.0.0.1", "10.0.0.2"
        hx = "10.0.1.1"
        a1, a2 = "10.0.10.1", "10.0.10.2"

        assert edge_types[tuple(sorted([c1, c2]))] == "peer"
        assert edge_types[tuple(sorted([c1, hx]))] == "uplink"
        assert edge_types[tuple(sorted([hx, a1]))] == "uplink"
        assert edge_types[tuple(sorted([hx, a2]))] == "uplink"
        assert edge_types[tuple(sorted([a1, a2]))] == "peer"
