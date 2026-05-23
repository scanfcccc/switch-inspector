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

    def _cat_for(cmd_name: str) -> str:
        p = registry._textfsm_parsers.get(cmd_name) or registry._custom_parsers.get(cmd_name)
        if p and p.fields:
            cats = {f.category for f in p.fields if f.category}
            return next(iter(cats)) if cats else 'unknown'
        return 'unknown'

    for lf in logs:
        device_ip = lf.device.ip or lf.filename_meta.ip
        device_name = lf.device.name or lf.filename_meta.name

        for cmd_name, cmd_block in lf.commands.items():
            result = registry.parse(cmd_name, cmd_block.raw)
            if result and result.rows:
                cmd_cat = _cat_for(cmd_name)
                for row in result.rows:
                    row['_device_ip'] = device_ip
                    row['_device_name'] = device_name
                    row['_device_serial'] = lf.device.serial or lf.filename_meta.serial
                    row['_source_file'] = lf.source_path
                    cat = row.pop('category', None) or cmd_cat
                    categories[cat].append(row)

    return dict(categories)


def merge_interface_rows(rows: List[Dict], device_rows: List[Dict] = None) -> List[Dict]:
    merged: Dict[str, Dict] = {}
    device_map = {}
    if device_rows:
        for dr in device_rows:
            ip = dr.get('_device_ip', '')
            if ip:
                device_map[ip] = dr

    for row in rows:
        key = row.get('normalized_iface', row.get('interface', ''))
        if not key:
            continue
        device_key = f"{row.get('_device_ip', '')}|{key}"
        if device_key in merged:
            merged[device_key].update(row)
        else:
            merged[device_key] = dict(row)

    result = list(merged.values())
    if device_map:
        for r in result:
            dip = r.get('_device_ip', '')
            if dip in device_map:
                for k, v in device_map[dip].items():
                    if k not in r or not r[k]:
                        r[k] = v
    return result


def merge_neighbor_rows(rows: List[Dict], device_rows: List[Dict] = None) -> List[Dict]:
    merged: Dict[str, Dict] = {}
    device_map = {}
    if device_rows:
        for dr in device_rows:
            ip = dr.get('_device_ip', '')
            if ip:
                device_map[ip] = dr

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

    result = list(merged.values())
    if device_map:
        for r in result:
            dip = r.get('_device_ip', '')
            if dip in device_map:
                for k, v in device_map[dip].items():
                    if k not in r or not r[k]:
                        r[k] = v
    return result


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
