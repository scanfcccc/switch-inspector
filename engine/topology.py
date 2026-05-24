"""LLDP topology inference engine.

Takes parsed_data (from field_catalog.parse_all_logs) and produces
a TopologyResult with nodes, edges, config, and summary for network
topology visualization.  Pure data transformation — no I/O, no main.py
imports, no HTTP.

Usage:
    result = build_topology(parsed_data)
    result = build_topology(parsed_data, config=my_config, show_terminals=True)
"""

from __future__ import annotations

import fnmatch
import ipaddress
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TIER_ORDER: Dict[str, int] = {"core": 0, "agg": 1, "access": 2, "terminal": 3}
_DOMAIN_RE = re.compile(r"\..*$")


@dataclass
class TopologyConfig:
    tier_patterns: Dict[str, List[str]] = field(default_factory=lambda: {
        "core": ["*CORE*", "*核心*"],
        "agg": ["*AGG*", "*汇聚*", "*HX*"],
        "access": ["*ACC*", "*接入*"],
    })
    building_map: Dict[str, str] = field(default_factory=lambda: {
        "*MZ*": "门诊楼", "*ZY*": "中医楼", "*XZ*": "行政楼",
        "*YW*": "医技楼", "*BW*": "病房楼",
    })
    internal_subnets: List[str] = field(default_factory=lambda: [
        "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
    ])
    default_tier: str = "access"
    default_device_type: str = "managed"


@dataclass
class TopologyNode:
    id: str
    name: str
    model: str
    tier: str
    group: str
    device_type: str


@dataclass
class TopologyEdge:
    source: str
    target: str
    links: List[dict] = field(default_factory=list)
    speed: str = ""
    type: str = "peer"
    count: int = 1


@dataclass
class TopologySummary:
    total_nodes: int = 0
    managed_devices: int = 0
    external_nodes: int = 0
    internal_links: int = 0
    external_links: int = 0


@dataclass
class TopologyResult:
    nodes: List[TopologyNode] = field(default_factory=list)
    edges: List[TopologyEdge] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    summary: TopologySummary = field(default_factory=TopologySummary)


def default_config() -> TopologyConfig:
    return TopologyConfig()


# ── Helpers ──────────────────────────────────────────────────────────

def _strip_domain(name: str) -> str:
    return _DOMAIN_RE.sub("", name).strip()


def _glob_match(name: str, patterns: List[str]) -> bool:
    return any(fnmatch.fnmatch(name, p) for p in patterns)


def _detect_tier(name: str, ip: str, config: TopologyConfig) -> str:
    for tier in ("core", "agg", "access"):
        patterns = config.tier_patterns.get(tier, [])
        if patterns and _glob_match(name, patterns):
            return tier
    if ip:
        if re.search(r"\d+\.\d+\.0\.\d+", ip):
            return "core"
        if re.search(r"\d+\.\d+\.1\.\d+", ip):
            return "agg"
    return config.default_tier


def _map_building(name: str, config: TopologyConfig) -> str:
    for pattern, building in config.building_map.items():
        if fnmatch.fnmatch(name, pattern):
            return building
    return "未分类"


def _ip_in_subnets(ip_str: str, subnets: List[str]) -> bool:
    if not ip_str:
        return False
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    for net_str in subnets:
        try:
            if addr in ipaddress.ip_network(net_str, strict=False):
                return True
        except ValueError:
            continue
    return False


def _get_edge_type(source_tier: str, target_tier: str) -> str:
    src = _TIER_ORDER.get(source_tier, 99)
    tgt = _TIER_ORDER.get(target_tier, 99)
    if src < tgt:
        return "uplink"
    if src == tgt:
        return "peer"
    return "access"


def _extract_speed(neighbor_model: str, neighbor_interface: str) -> str:
    src = neighbor_model or ""
    m = re.search(r"(\d+)\s*G(?:bit|BASE)", src, re.IGNORECASE)
    if m:
        return f"{m.group(1)}G"
    m = re.search(r"(\d+)\s*GE", src, re.IGNORECASE)
    if m:
        return f"{m.group(1)}G"
    iface = neighbor_interface or ""
    speed_map = {
        "HundredGigabitEthernet": "100G", "FortyGigabitEthernet": "40G",
        "TwentyFiveGigabitEthernet": "25G", "TenGigabitEthernet": "10G",
        "GigabitEthernet": "1G", "FastEthernet": "100M",
    }
    for prefix, speed in speed_map.items():
        if iface.startswith(prefix):
            return speed
    return ""


# ── Node extraction ──────────────────────────────────────────────────

def _resolve_node_id(
    ip: str,
    name: str,
    nodes: Dict[str, TopologyNode],
    device_by_ip: Dict[str, dict],
    device_by_name: Dict[str, dict],
    device_by_norm: Dict[str, dict],
) -> Optional[str]:
    if ip and ip in nodes:
        return ip
    if ip and ip in device_by_ip:
        return ip
    if not name:
        return None
    nl = name.lower()
    nn = _strip_domain(name).lower()
    for nid, node in nodes.items():
        if node.name.lower() == nl:
            return nid
    for nid, node in nodes.items():
        if _strip_domain(node.name).lower() == nn:
            return nid
    if nl in device_by_name:
        return device_by_name[nl].get("_device_ip") or nl
    if nn in device_by_norm:
        return device_by_norm[nn].get("_device_ip") or nn
    return None


def _extract_nodes(
    parsed_data: Dict[str, List[Dict]],
    config: TopologyConfig,
) -> Dict[str, TopologyNode]:
    nodes: Dict[str, TopologyNode] = {}
    device_rows = parsed_data.get("device", [])
    neighbor_rows = parsed_data.get("neighbor", [])

    # Index known devices by IP, name, normalized name.
    device_by_ip: Dict[str, dict] = {}
    device_by_name: Dict[str, dict] = {}
    device_by_norm: Dict[str, dict] = {}
    for dr in device_rows:
        ip = (dr.get("_device_ip") or "").strip()
        name = (dr.get("_device_name") or "").strip()
        if ip:
            device_by_ip[ip] = dr
        if name:
            device_by_name[name.lower()] = dr
            device_by_norm[_strip_domain(name).lower()] = dr

    # Collect all scanned (local) devices: from device rows and neighbor
    # source IPs (a device may lack `show version` but still have LLDP data).
    local_by_id: Dict[str, dict] = {}
    for dr in device_rows:
        ip = (dr.get("_device_ip") or "").strip()
        name = (dr.get("_device_name") or "").strip()
        nid = ip if ip else name
        if nid and nid not in local_by_id:
            local_by_id[nid] = {
                "name": name or nid, "ip": ip,
                "model": (dr.get("model") or dr.get("system_description") or ""),
            }
    for nr in neighbor_rows:
        src_ip = (nr.get("_device_ip") or "").strip()
        src_name = (nr.get("_device_name") or "").strip()
        already_known = (
            (src_ip and src_ip in device_by_ip)
            or (src_name and src_name.lower() in device_by_name)
            or (src_name and _strip_domain(src_name).lower() in device_by_norm)
        )
        if already_known:
            continue
        nid = src_ip if src_ip else src_name
        if nid and nid not in local_by_id:
            local_by_id[nid] = {"name": src_name or nid, "ip": src_ip, "model": ""}

    # Register managed nodes.
    for nid, info in local_by_id.items():
        name = info["name"]
        nodes[nid] = TopologyNode(
            id=nid, name=name, model=info["model"][:60],
            tier=_detect_tier(name, info["ip"], config),
            group=_map_building(name, config),
            device_type="managed",
        )

    # Process neighbor targets: match against known devices or create external.
    for nr in neighbor_rows:
        n_ip = (nr.get("neighbor_ip") or "").strip()
        n_name = (nr.get("neighbor_name") or "").strip()
        n_model = (nr.get("neighbor_model") or "")
        if not n_ip and not n_name:
            continue
        if _resolve_node_id(n_ip, n_name, nodes, device_by_ip,
                             device_by_name, device_by_norm):
            continue
        nid = n_ip if n_ip else _strip_domain(n_name)
        if not nid or nid in nodes:
            continue
        nodes[nid] = TopologyNode(
            id=nid, name=n_name or nid, model=n_model[:60],
            tier=_detect_tier(n_name or nid, n_ip, config),
            group=_map_building(n_name or nid, config),
            device_type="external",
        )

    return nodes


# ── Edge building & dedup ────────────────────────────────────────────

def _build_edges(
    parsed_data: Dict[str, List[Dict]],
    nodes: Dict[str, TopologyNode],
) -> List[TopologyEdge]:
    neighbor_rows = parsed_data.get("neighbor", [])
    device_rows = parsed_data.get("device", [])

    device_by_ip: Dict[str, dict] = {}
    device_by_name: Dict[str, dict] = {}
    device_by_norm: Dict[str, dict] = {}
    for dr in device_rows:
        ip = (dr.get("_device_ip") or "").strip()
        name = (dr.get("_device_name") or "").strip()
        if ip:
            device_by_ip[ip] = dr
        if name:
            device_by_name[name.lower()] = dr
            device_by_norm[_strip_domain(name).lower()] = dr

    edge_map: Dict[tuple, dict] = {}

    for nr in neighbor_rows:
        src_ip = (nr.get("_device_ip") or "").strip()
        src_name = (nr.get("_device_name") or "").strip()
        tgt_ip = (nr.get("neighbor_ip") or "").strip()
        tgt_name = (nr.get("neighbor_name") or "").strip()
        tgt_iface = (nr.get("neighbor_interface") or "").strip()
        local_iface = (nr.get("local_iface") or nr.get("interface") or "").strip()
        tgt_model = (nr.get("neighbor_model") or "").strip()

        source_id = _resolve_node_id(src_ip, src_name, nodes,
                                     device_by_ip, device_by_name, device_by_norm)
        target_id = _resolve_node_id(tgt_ip, tgt_name, nodes,
                                     device_by_ip, device_by_name, device_by_norm)
        if not source_id or not target_id:
            logger.warning("Skipping row: unresolvable source=(%s,%s) target=(%s,%s)",
                           src_ip, src_name, tgt_ip, tgt_name)
            continue
        if source_id == target_id:
            continue  # self-loop

        edge_key = tuple(sorted([source_id, target_id]))
        link = {"source_port": local_iface, "target_port": tgt_iface}

        if edge_key in edge_map:
            edge_map[edge_key]["count"] += 1
            edge_map[edge_key]["links"].append(link)
        else:
            edge_map[edge_key] = {
                "source": source_id, "target": target_id,
                "links": [link], "speed": _extract_speed(tgt_model, tgt_iface),
                "count": 1,
            }

    edges: List[TopologyEdge] = []
    for info in edge_map.values():
        src_node = nodes.get(info["source"])
        tgt_node = nodes.get(info["target"])
        edges.append(TopologyEdge(
            source=info["source"], target=info["target"],
            links=info["links"], speed=info["speed"],
            type=_get_edge_type(
                src_node.tier if src_node else "access",
                tgt_node.tier if tgt_node else "access",
            ),
            count=info["count"],
        ))
    return edges


# ── Terminal detection ───────────────────────────────────────────────

def _detect_terminals(
    parsed_data: Dict[str, List[Dict]],
    nodes: Dict[str, TopologyNode],
    config: TopologyConfig,
) -> None:
    """Mark leaf devices that only appear as neighbour targets with no
    matching device entry as terminals.  Infrastructure-class devices
    (matching core/agg/access name patterns) are exempt."""

    infra_patterns: List[str] = []
    for tier in ("core", "agg", "access"):
        infra_patterns.extend(config.tier_patterns.get(tier, []))

    known_identifiers: set = set()
    for dr in parsed_data.get("device", []):
        ip = (dr.get("_device_ip") or "").strip()
        name = (dr.get("_device_name") or "").strip()
        if ip:
            known_identifiers.add(ip)
        if name:
            known_identifiers.add(name.lower())
            known_identifiers.add(_strip_domain(name).lower())

    source_ids: set = set()
    for nr in parsed_data.get("neighbor", []):
        src_ip = (nr.get("_device_ip") or "").strip()
        src_name = (nr.get("_device_name") or "").strip()
        if src_ip:
            source_ids.add(src_ip)
        if src_name:
            source_ids.add(src_name.lower())
            source_ids.add(_strip_domain(src_name).lower())

    for node in nodes.values():
        if node.device_type != "external":
            continue
        if _glob_match(node.name, infra_patterns):
            continue
        nid_lower = node.id.lower()
        name_lower = node.name.lower()
        name_norm = _strip_domain(name_lower)
        is_known = (nid_lower in known_identifiers or name_lower in known_identifiers
                    or name_norm in known_identifiers)
        is_source = (nid_lower in source_ids or name_lower in source_ids
                     or name_norm in source_ids)
        if not is_known and not is_source:
            node.tier = "terminal"
            node.device_type = "external"


# ── Public entry point ───────────────────────────────────────────────

def build_topology(
    parsed_data: Dict[str, List[Dict]],
    config: Optional[TopologyConfig] = None,
    show_terminals: bool = False,
) -> TopologyResult:
    if config is None:
        config = default_config()

    if not parsed_data or not any(parsed_data.values()):
        return TopologyResult(
            config={"show_terminals": show_terminals, "show_external": True},
            summary=TopologySummary(),
        )

    try:
        nodes = _extract_nodes(parsed_data, config)
    except Exception:
        logger.warning("Node extraction failed", exc_info=True)
        nodes = {}

    try:
        _detect_terminals(parsed_data, nodes, config)
    except Exception:
        logger.warning("Terminal detection failed", exc_info=True)

    try:
        edges = _build_edges(parsed_data, nodes)
    except Exception:
        logger.warning("Edge building failed", exc_info=True)
        edges = []

    if not show_terminals:
        terminal_ids = {n.id for n in nodes.values() if n.tier == "terminal"}
        nodes = {nid: n for nid, n in nodes.items() if nid not in terminal_ids}
        edges = [e for e in edges
                 if e.source not in terminal_ids and e.target not in terminal_ids]

    managed_count = sum(1 for n in nodes.values() if n.device_type == "managed")
    external_count = sum(1 for n in nodes.values() if n.device_type == "external")
    internal_links = 0
    external_links = 0
    for e in edges:
        src = nodes.get(e.source)
        tgt = nodes.get(e.target)
        if src and tgt and src.device_type == "managed" and tgt.device_type == "managed":
            internal_links += 1
        else:
            external_links += 1

    return TopologyResult(
        nodes=list(nodes.values()),
        edges=edges,
        config={"show_terminals": show_terminals, "show_external": True},
        summary=TopologySummary(
            total_nodes=len(nodes),
            managed_devices=managed_count,
            external_nodes=external_count,
            internal_links=internal_links,
            external_links=external_links,
        ),
    )
