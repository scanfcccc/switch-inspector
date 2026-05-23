#!/usr/bin/env python3
import os
import sys
import json
import threading
from pathlib import Path
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn
import aiofiles

from engine.splitter import split_log_file, LogFile
from engine.registry import ParserRegistry
from engine.field_catalog import (
    build_catalog, parse_all_logs, merge_interface_rows,
    merge_neighbor_rows, project_rows, Catalog,
)
from engine.exporter import export_csv, export_xlsx
from engine.report import build_report


# --- Scan state (thread-safe, single-user local tool) ---
registry = ParserRegistry()
catalog: Optional[Catalog] = None
_scan_lock = threading.Lock()
_scan_state = {
    "parsed_data": {},
    "logs": [],
    "scan_path": "",
}


def initialize():
    global registry, catalog
    if catalog is not None:
        return
    registry.initialize()
    catalog = build_catalog(registry)


def get_state():
    with _scan_lock:
        return _scan_state["parsed_data"], _scan_state["logs"], _scan_state["scan_path"]


def set_state(parsed_data, logs, scan_path):
    with _scan_lock:
        _scan_state["parsed_data"] = parsed_data
        _scan_state["logs"] = logs
        _scan_state["scan_path"] = scan_path


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    from engine.hot_reload import auto_start, auto_stop
    watcher = auto_start()
    yield
    auto_stop()


app = FastAPI(title="switch-inspector", lifespan=lifespan)


# --- API routes ---

@app.get("/", response_class=HTMLResponse)
async def index():
    async with aiofiles.open("ui/templates/index.html", encoding="utf-8") as f:
        html = await f.read()
    return html


@app.post("/api/scan")
async def api_scan(body: dict):
    path = body.get("path", "")
    if not path or not os.path.isdir(path):
        set_state({}, [], "")
        return {"error": f"目录不存在: {path}"}

    log_files = sorted(Path(path).rglob("*.log"))
    if not log_files:
        set_state({}, [], "")
        return {"error": f"在 {path} 中未找到 .log 文件"}

    logs = []
    errors = []
    for lf in log_files:
        try:
            logs.append(split_log_file(str(lf)))
        except Exception as e:
            errors.append(f"{lf.name}: {e}")

    parsed_data = parse_all_logs(logs, registry)
    set_state(parsed_data, logs, path)

    # get field groups
    device_fields = [f for f in catalog.fields if f.category == 'device']
    interface_fields = [f for f in catalog.fields if f.category == 'interface']
    neighbor_fields = [f for f in catalog.fields if f.category == 'neighbor']
    system_fields = [f for f in catalog.fields if f.category == 'system']
    log_fields = [f for f in catalog.fields if f.category == 'log']

    field_groups = {}
    if device_fields: field_groups['device'] = [{'key': f.key, 'label': f.label} for f in device_fields]
    if interface_fields: field_groups['interface'] = [{'key': f.key, 'label': f.label} for f in interface_fields]
    if neighbor_fields: field_groups['neighbor'] = [{'key': f.key, 'label': f.label} for f in neighbor_fields]
    if system_fields: field_groups['system'] = [{'key': f.key, 'label': f.label} for f in system_fields]
    if log_fields: field_groups['log'] = [{'key': f.key, 'label': f.label} for f in log_fields]

    all_cmds = set()
    for lf in logs:
        all_cmds.update(lf.commands.keys())

    structured_errors = registry.get_structured_load_errors()
    failed_critical = sum(1 for e in structured_errors if e["severity"] == "critical")
    failed_warning = sum(1 for e in structured_errors if e["severity"] == "warning")
    plugin_status = {
        "loaded": len(registry._custom_parsers) + len(registry._textfsm_parsers),
        "failed_critical": failed_critical,
        "failed_warning": failed_warning,
        "errors": structured_errors,
    }

    all_warnings = errors[:10]
    if structured_errors:
        all_warnings.extend([f"[解析器] {e['message']}" for e in structured_errors[:5]])

    return {
        "file_count": len(log_files),
        "device_count": len(logs),
        "command_count": len(all_cmds),
        "field_count": len(catalog.fields),
        "field_groups": field_groups,
        "warnings": all_warnings,
        "plugin_status": plugin_status,
    }


CAT_PRIORITY = ['interface', 'neighbor', 'device', 'system', 'log']


def _build_rows(field_keys: List[str]) -> tuple:
    parsed_data, _, _ = get_state()
    if not field_keys or not parsed_data:
        return [], {}, "interface"
    field_defs = {f.key: f for f in catalog.fields}
    cat_keys = {}
    for key in field_keys:
        fd = field_defs.get(key)
        if fd:
            cat_keys.setdefault(fd.category, []).append(key)

    device_rows = parsed_data.get('device', [])
    primary_cat = next((c for c in CAT_PRIORITY if c in cat_keys), 'interface')

    all_cat_rows = parsed_data.get(primary_cat, [])
    if primary_cat == 'interface':
        all_cat_rows = merge_interface_rows(all_cat_rows, device_rows)
    elif primary_cat == 'neighbor':
        all_cat_rows = merge_neighbor_rows(all_cat_rows)

    primary_keys = cat_keys.get(primary_cat, [])
    merged = project_rows(all_cat_rows, primary_keys)
    for row in merged:
        row['_row_type'] = primary_cat

    for cat in cat_keys:
        if cat == primary_cat or cat == 'device':
            continue
        extra_keys = cat_keys[cat]
        extra_rows = parsed_data.get(cat, [])
        if cat == 'interface':
            extra_rows = merge_interface_rows(extra_rows, device_rows)
        elif cat == 'neighbor':
            extra_rows = merge_neighbor_rows(extra_rows, device_rows)
        extra_rows = project_rows(extra_rows, extra_keys)
        for row in extra_rows:
            row['_row_type'] = cat
        merged.extend(extra_rows)

    return merged, field_defs, primary_cat


@app.post("/api/preview")
async def api_preview(body: dict):
    fields = body.get("fields", [])
    page = body.get("page", 1)
    page_size = body.get("page_size", 100)

    merged, field_defs, primary_cat = _build_rows(fields)
    total = len(merged)
    label_map = {f.key: f.label for f in catalog.fields}

    columns = []
    for k in fields:
        if k in label_map:
            label = label_map[k]
            if label not in columns:
                columns.append(label)

    start = (page - 1) * page_size
    end = start + page_size
    page_rows = merged[start:end]

    result_rows = []
    for i, row in enumerate(page_rows):
        r = {'_rowid': start + i, '_row_type': row.get('_row_type', '')}
        for k in fields:
            fd = field_defs.get(k)
            label = fd.label if fd else k
            r[label] = row.get(k, '')
        result_rows.append(r)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "columns": columns,
        "rows": result_rows,
        "row_type": primary_cat,
    }


@app.get("/api/export")
async def api_export(fields: str, format: str = "csv"):
    field_keys = [k.strip() for k in fields.split(",") if k.strip()]
    merged, field_defs, primary_cat = _build_rows(field_keys)

    if format == "xlsx":
        data = export_xlsx(merged, catalog.fields, field_keys)
        return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": "attachment; filename=switch_report.xlsx"})
    else:
        data = export_csv(merged, catalog.fields, field_keys)
        return Response(content=data, media_type="text/csv; charset=utf-8-sig",
                        headers={"Content-Disposition": "attachment; filename=switch_report.csv"})


@app.post("/api/report")
async def api_report():
    parsed_data, _, _ = get_state()
    if not parsed_data:
        return {"error": "请先扫描目录"}
    device_rows = parsed_data.get('device', [])
    iface_rows = merge_interface_rows(parsed_data.get('interface', []), device_rows)
    report = build_report(iface_rows, device_rows, parsed_data)
    return {
        "total_devices": report.total_devices,
        "total_interfaces": report.total_interfaces,
        "up_interfaces": report.up_interfaces,
        "down_interfaces": report.down_interfaces,
        "optical_healthy": report.optical_healthy,
        "optical_warning": report.optical_warning,
        "optical_critical": report.optical_critical,
        "alerts": [{"severity": a.severity, "category": a.category,
                     "device": f"{a.device_name}({a.device_ip})",
                     "message": a.message}
                    for a in report.alerts],
        "devices": [{"ip": d.ip, "name": d.name, "model": d.model,
                      "interfaces": d.interface_count,
                      "up": d.up_count, "down": d.down_count,
                      }
                     for d in report.devices],
    }


def run():
    port = int(os.environ.get("PORT", 9876))
    print(f"  switch-inspector starting at http://127.0.0.1:{port}")
    uvicorn.run("main:app", host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    run()
