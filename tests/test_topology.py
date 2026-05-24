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
    _resolve_node_id,
    _extract_nodes,
    _build_edges,
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


# ── _resolve_node_id ───────────────────────────────────────────────────

class TestResolveNodeId:

    def _make_nodes(self):
        nodes: dict = {}
        nodes["10.0.0.1"] = TopologyNode(
            id="10.0.0.1", name="CORE-SW-01", model="",
            tier="core", group="", device_type="managed",
        )
        nodes["10.0.0.2"] = TopologyNode(
            id="10.0.0.2", name="CORE-SW-02.domain.com", model="",
            tier="core", group="", device_type="managed",
        )
        return nodes

    def _make_indexes(self):
        device_by_ip = {
            "10.0.0.1": {"_device_ip": "10.0.0.1", "_device_name": "CORE-SW-01"},
            "10.0.0.2": {"_device_ip": "10.0.0.2", "_device_name": "CORE-SW-02.domain.com"},
            "10.0.0.3": {"_device_ip": "10.0.0.3", "_device_name": "DEVICE-FROM-INDEX"},
        }
        device_by_name = {
            "core-sw-01": {"_device_ip": "10.0.0.1", "_device_name": "CORE-SW-01"},
            "core-sw-02.domain.com": {"_device_ip": "10.0.0.2", "_device_name": "CORE-SW-02.domain.com"},
            "device-from-index": {"_device_ip": "10.0.0.3", "_device_name": "DEVICE-FROM-INDEX"},
        }
        device_by_norm = {
            "core-sw-01": {"_device_ip": "10.0.0.1", "_device_name": "CORE-SW-01"},
            "core-sw-02": {"_device_ip": "10.0.0.2", "_device_name": "CORE-SW-02.domain.com"},
            "device-from-index": {"_device_ip": "10.0.0.3", "_device_name": "DEVICE-FROM-INDEX"},
        }
        return device_by_ip, device_by_name, device_by_norm

    # 1. IP match → returns IP
    def test_ip_match(self):
        nodes = self._make_nodes()
        dip, dnm, dno = self._make_indexes()
        result = _resolve_node_id("10.0.0.1", "", nodes, dip, dnm, dno)
        assert result == "10.0.0.1"

    # 2. Name exact match (case-insensitive) → returns node id
    def test_name_exact_match_case_insensitive(self):
        nodes = self._make_nodes()
        dip, dnm, dno = self._make_indexes()
        result = _resolve_node_id("", "CORE-SW-01", nodes, dip, dnm, dno)
        assert result == "10.0.0.1"
        # Lowercase name also matches
        result2 = _resolve_node_id("", "core-sw-01", nodes, dip, dnm, dno)
        assert result2 == "10.0.0.1"

    # 3. Name normalized (domain stripped) → returns node id
    def test_name_normalized_domain_stripped(self):
        nodes = self._make_nodes()
        dip, dnm, dno = self._make_indexes()
        result = _resolve_node_id("", "CORE-SW-02", nodes, dip, dnm, dno)
        assert result == "10.0.0.2"

    # 4. device_by_name fallback → returns device_ip
    def test_device_by_name_fallback(self):
        nodes = self._make_nodes()
        dip, dnm, dno = self._make_indexes()
        result = _resolve_node_id("", "DEVICE-FROM-INDEX", nodes, dip, dnm, dno)
        assert result == "10.0.0.3"

    # 5. device_by_norm fallback → returns device_ip
    def test_device_by_norm_fallback(self):
        nodes = self._make_nodes()
        dip, dnm, dno = self._make_indexes()
        result = _resolve_node_id("", "device-from-index.domain.com",
                                  nodes, dip, dnm, dno)
        assert result == "10.0.0.3"

    # 6. IP no match → None
    def test_ip_no_match(self):
        nodes = self._make_nodes()
        dip, dnm, dno = self._make_indexes()
        result = _resolve_node_id("9.9.9.9", "", nodes, dip, dnm, dno)
        assert result is None

    # 7. Name no match → None
    def test_name_no_match(self):
        nodes = self._make_nodes()
        dip, dnm, dno = self._make_indexes()
        result = _resolve_node_id("", "UNKNOWN", nodes, dip, dnm, dno)
        assert result is None

    # 8. Empty input → None
    def test_empty_input(self):
        nodes = self._make_nodes()
        dip, dnm, dno = self._make_indexes()
        result = _resolve_node_id("", "", nodes, dip, dnm, dno)
        assert result is None

    # 9. IP priority over name → returns IP's node
    def test_ip_priority_over_name(self):
        nodes = self._make_nodes()
        dip, dnm, dno = self._make_indexes()
        result = _resolve_node_id("10.0.0.1", "different-name",
                                  nodes, dip, dnm, dno)
        assert result == "10.0.0.1"

    # 10. chassis_id match → returns node id
    def test_chassis_id_match(self):
        nodes = self._make_nodes()
        dip, dnm, dno = self._make_indexes()
        dch = {"aa:bb:cc:dd:ee:ff":
               {"_device_ip": "10.0.0.3", "_device_name": "DEVICE-FROM-INDEX"}}
        result = _resolve_node_id("", "", nodes, dip, dnm, dno,
                                  "aa:bb:cc:dd:ee:ff", dch)
        assert result == "10.0.0.3"

    # 11. IP priority over chassis_id → returns IP's node
    def test_ip_priority_over_chassis_id(self):
        nodes = self._make_nodes()
        dip, dnm, dno = self._make_indexes()
        dch = {"aa:bb:cc:dd:ee:ff":
               {"_device_ip": "9.9.9.9", "_device_name": "OTHER-DEVICE"}}
        result = _resolve_node_id("10.0.0.1", "", nodes, dip, dnm, dno,
                                  "aa:bb:cc:dd:ee:ff", dch)
        assert result == "10.0.0.1"


# ── _extract_nodes dedup ────────────────────────────────────────────────

class TestExtractNodesDedup:

    def test_same_src_ip_two_rows(self, topo_config):
        """Two neighbor rows with same src_ip (no device list) → 1 managed node."""
        data = {
            "device": [],
            "neighbor": [
                {"_device_ip": "10.0.0.99", "_device_name": "DEV-99",
                 "neighbor_name": "OTHER-A", "neighbor_ip": "10.0.0.1"},
                {"_device_ip": "10.0.0.99", "_device_name": "DEV-99",
                 "neighbor_name": "OTHER-B", "neighbor_ip": "10.0.0.2"},
            ],
        }
        nodes = _extract_nodes(data, topo_config)
        ip_nodes = [n for n in nodes.values() if n.id == "10.0.0.99"]
        assert len(ip_nodes) == 1

    def test_same_src_name_two_rows(self, topo_config):
        """Two neighbor rows with same src_name (no src_ip, no device list) → 1 managed node."""
        data = {
            "device": [],
            "neighbor": [
                {"_device_ip": "", "_device_name": "DEV-99",
                 "neighbor_name": "OTHER-A", "neighbor_ip": "10.0.0.1"},
                {"_device_ip": "", "_device_name": "DEV-99",
                 "neighbor_name": "OTHER-B", "neighbor_ip": "10.0.0.2"},
            ],
        }
        nodes = _extract_nodes(data, topo_config)
        name_nodes = [n for n in nodes.values() if n.name == "DEV-99"]
        assert len(name_nodes) == 1

    def test_src_ip_already_in_local_by_id(self, topo_config):
        """src_ip matches existing local_by_id entry with different nid → skip."""
        data = {
            "device": [],
            "neighbor": [
                {"_device_ip": "10.0.0.99", "_device_name": "DEV-99",
                 "neighbor_name": "OTHER-A", "neighbor_ip": "10.0.0.1"},
                {"_device_ip": "", "_device_name": "DEV-99",
                 "neighbor_name": "OTHER-B", "neighbor_ip": "10.0.0.2"},
            ],
        }
        nodes = _extract_nodes(data, topo_config)
        dev_nodes = [n for n in nodes.values() if "DEV-99" in n.name or n.id == "10.0.0.99"]
        assert len(dev_nodes) == 1
        assert "10.0.0.99" in nodes

    def test_src_name_already_in_local_by_id(self, topo_config):
        """src_name matches existing local_by_id entry → skip."""
        data = {
            "device": [],
            "neighbor": [
                {"_device_ip": "", "_device_name": "DEV-99",
                 "neighbor_name": "OTHER-A", "neighbor_ip": "10.0.0.1"},
                {"_device_ip": "10.0.0.99", "_device_name": "DEV-99",
                 "neighbor_name": "OTHER-B", "neighbor_ip": "10.0.0.2"},
            ],
        }
        nodes = _extract_nodes(data, topo_config)
        dev_nodes = [n for n in nodes.values() if "DEV-99" in n.name or "10.0.0.99" in n.id]
        assert len(dev_nodes) == 1


# ── _detect_tier extended ──────────────────────────────────────────────

class TestDetectTierExtended:

    def test_chinese_core(self, topo_config):
        assert _detect_tier("核心交换机-01", "", topo_config) == "core"

    def test_chinese_agg(self, topo_config):
        assert _detect_tier("汇聚交换机-F2", "", topo_config) == "agg"

    def test_chinese_access(self, topo_config):
        assert _detect_tier("接入交换机-B1", "", topo_config) == "access"

    def test_real_acc_name(self, topo_config):
        assert _detect_tier(
            "PJXRMYY-ACC-NW-MZ-3F-04-S5000-210-POE", "", topo_config
        ) == "access"

    def test_real_core_name(self, topo_config):
        assert _detect_tier(
            "PJXRMYY-NW-JF-2F-CORE", "", topo_config
        ) == "core"

    def test_real_agg_name(self, topo_config):
        assert _detect_tier(
            "PJXRMYY-NW-MZ-1#-1~3F-AGG-S6120-01-30", "", topo_config
        ) == "agg"

    def test_ip_172_core(self, topo_config):
        assert _detect_tier("unknown", "172.17.0.1", topo_config) == "core"

    def test_ip_172_agg(self, topo_config):
        assert _detect_tier("unknown", "172.17.1.1", topo_config) == "agg"

    def test_ip_172_fallback(self, topo_config):
        assert _detect_tier("unknown", "172.17.252.1", topo_config) == "access"

    def test_empty_name_empty_ip(self, topo_config):
        assert _detect_tier("", "", topo_config) == "access"

    def test_name_only_no_ip(self, topo_config):
        assert _detect_tier("CORE-SW", "", topo_config) == "core"

    def test_multi_pattern_match(self, topo_config):
        """Name matching both *CORE* and *ACC* → core (higher priority than access)."""
        assert _detect_tier("CORE-ACC-SW", "", topo_config) == "core"


# ── _map_building extended ─────────────────────────────────────────────

class TestMapBuildingExtended:

    def test_real_mz(self, topo_config):
        assert _map_building(
            "PJXRMYY-ACC-NW-MZ-3F-04-S5000-210-POE", topo_config
        ) == "门诊楼"

    def test_real_zy(self, topo_config):
        assert _map_building(
            "PJXRMYY-ACC-NW-ZY-12F-01-S5000-100", topo_config
        ) == "中医楼"

    def test_real_xz(self, topo_config):
        assert _map_building(
            "PJXRMYY-ACC-NW-XZ-2F-S5000-50", topo_config
        ) == "行政楼"

    def test_real_jf(self, topo_config):
        assert _map_building(
            "PJXRMYY-NW-JF-2F-CORE", topo_config
        ) == "未分类"


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


# ── _build_edges direction ──────────────────────────────────────────────

class TestBuildEdgesDirection:

    def test_self_loop_filtered(self, topo_config):
        """Neighbor row where source == target → 0 edges."""
        data = {
            "device": [
                {"_device_name": "SW-01", "_device_ip": "10.0.0.1", "model": ""},
            ],
            "neighbor": [
                {"_device_name": "SW-01", "_device_ip": "10.0.0.1",
                 "neighbor_name": "SW-01", "neighbor_ip": "10.0.0.1",
                 "interface": "Gi0/1", "neighbor_interface": "Gi0/1"},
            ],
        }
        nodes = _extract_nodes(data, topo_config)
        edges = _build_edges(data, nodes)
        assert len(edges) == 0

    def test_multi_edge_same_target(self, topo_config):
        """Two neighbor rows, same source+target, different ports → 1 edge, count=2."""
        data = {
            "device": [
                {"_device_name": "SW-01", "_device_ip": "10.0.0.1", "model": ""},
                {"_device_name": "SW-02", "_device_ip": "10.0.0.2", "model": ""},
            ],
            "neighbor": [
                {"_device_name": "SW-01", "_device_ip": "10.0.0.1",
                 "neighbor_name": "SW-02", "neighbor_ip": "10.0.0.2",
                 "interface": "Gi0/1", "neighbor_interface": "Gi0/1"},
                {"_device_name": "SW-01", "_device_ip": "10.0.0.1",
                 "neighbor_name": "SW-02", "neighbor_ip": "10.0.0.2",
                 "interface": "Gi0/2", "neighbor_interface": "Gi0/2"},
            ],
        }
        nodes = _extract_nodes(data, topo_config)
        edges = _build_edges(data, nodes)
        assert len(edges) == 1
        assert edges[0].count == 2

    def test_canonical_dedup(self, topo_config):
        """A→B and B→A neighbor rows → 1 edge, count=2."""
        data = {
            "device": [
                {"_device_name": "SW-01", "_device_ip": "10.0.0.1", "model": ""},
                {"_device_name": "SW-02", "_device_ip": "10.0.0.2", "model": ""},
            ],
            "neighbor": [
                {"_device_name": "SW-01", "_device_ip": "10.0.0.1",
                 "neighbor_name": "SW-02", "neighbor_ip": "10.0.0.2",
                 "interface": "Gi0/1", "neighbor_interface": "Gi0/1"},
                {"_device_name": "SW-02", "_device_ip": "10.0.0.2",
                 "neighbor_name": "SW-01", "neighbor_ip": "10.0.0.1",
                 "interface": "Gi0/1", "neighbor_interface": "Gi0/1"},
            ],
        }
        nodes = _extract_nodes(data, topo_config)
        edges = _build_edges(data, nodes)
        assert len(edges) == 1
        assert edges[0].count == 2
