from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from engine.splitter import LogFile
from engine.registry import ParserRegistry
from engine.parser_base import FieldDef


@dataclass
class Catalog:
    fields: List[FieldDef] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)


def build_catalog(registry: ParserRegistry) -> Catalog:
    fields = registry.all_fields()
    cats = sorted(set(f.category for f in fields))
    return Catalog(fields=fields, categories=cats)


def get_fields_by_category(catalog: Catalog, category: str) -> List[FieldDef]:
    return [f for f in catalog.fields if f.category == category]


def parse_all_logs(logs: List[LogFile], registry: ParserRegistry) -> Dict[str, List[Dict]]:
    categories: Dict[str, List[Dict]] = defaultdict(list)

    for lf in logs:
        device_ip = lf.device.ip or lf.filename_meta.ip
        device_name = lf.device.name or lf.filename_meta.name

        for cmd_name, cmd_block in lf.commands.items():
            result = registry.parse(cmd_name, cmd_block.raw)
            if result and result.rows:
                for row in result.rows:
                    row['_device_ip'] = device_ip
                    row['_device_name'] = device_name
                    row['_device_serial'] = lf.device.serial or lf.filename_meta.serial
                    row['_source_file'] = lf.source_path
                    cat = row.get('category', 'unknown')
                    categories[cat].append(row)

    return dict(categories)


def merge_interface_rows(rows: List[Dict]) -> List[Dict]:
    merged: Dict[str, Dict] = {}
    for row in rows:
        key = row.get('normalized_iface', row.get('interface', ''))
        if not key:
            continue
        device_key = f"{row.get('_device_ip', '')}|{key}"
        if device_key in merged:
            merged[device_key].update(row)
        else:
            merged[device_key] = dict(row)

    return list(merged.values())


def merge_neighbor_rows(rows: List[Dict]) -> List[Dict]:
    merged: Dict[str, Dict] = {}
    for row in rows:
        key = row.get('local_iface', row.get('interface', ''))
        neighbor = row.get('neighbor_name', '')
        if not key:
            continue
        device_key = f"{row.get('_device_ip', '')}|{key}|{neighbor}"
        if device_key in merged:
            merged[device_key].update(row)
        else:
            merged[device_key] = dict(row)
    return list(merged.values())


def project_rows(rows: List[Dict], selected_keys: List[str]) -> List[Dict]:
    if not selected_keys:
        return rows

    default_keys = ['_device_ip', '_device_name', '_device_serial', '_source_file']
    result = []
    for row in rows:
        projected = {}
        for key in selected_keys:
            if key in row:
                projected[key] = row[key]
        for dk in default_keys:
            if dk in row:
                projected[dk] = row[dk]
        if projected:
            result.append(projected)
    return result


def get_category_groups(categories: Dict[str, List[Dict]]) -> Dict[str, str]:
    join_map = {
        'interface': '按接口聚合',
        'neighbor': '按邻居聚合',
        'device': '每设备一行',
        'system': '每设备一行',
        'log': '每条日志一行',
    }
    return {cat: join_map.get(cat, '独立') for cat in categories}
