#!/usr/bin/env python3
import os
import sys
import json
import webbrowser
from pathlib import Path
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
import uvicorn

from engine.splitter import split_log_file, LogFile
from engine.registry import ParserRegistry
from engine.field_catalog import (
    build_catalog, parse_all_logs, merge_interface_rows,
    merge_neighbor_rows, project_rows, Catalog,
)
from engine.exporter import export_csv, export_xlsx


# --- Global state ---
registry = ParserRegistry()
catalog: Optional[Catalog] = None
logs: List[LogFile] = []
parsed_data: dict = {}  # category -> rows


def initialize():
    global registry, catalog
    if catalog is not None:
        return
    registry.initialize()
    catalog = build_catalog(registry)


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    yield


app = FastAPI(title="switch-inspector", lifespan=lifespan)


# --- HTML templates ---
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>switch-inspector</title>
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<script src="https://unpkg.com/alpinejs@3.14.8" defer></script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Microsoft YaHei', sans-serif; background: #f0f2f5; color: #333; }
.header { background: #1a73e8; color: #fff; padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
.header h1 { font-size: 20px; font-weight: 600; }
.header span { font-size: 13px; opacity: 0.85; }
.container { max-width: 1400px; margin: 0 auto; padding: 20px; }
.card { background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,.1); padding: 20px; margin-bottom: 16px; }
.scan-bar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.scan-bar input[type=text] { flex: 1; min-width: 300px; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 14px; }
.scan-bar button { padding: 8px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.btn-primary { background: #1a73e8; color: #fff; }
.btn-primary:hover { background: #1557b0; }
.btn-success { background: #52c41a; color: #fff; }
.btn-success:hover { background: #389e0d; }
.btn-export { background: #fa8c16; color: #fff; }
.btn-export:hover { background: #d46b08; }
.layout { display: flex; gap: 16px; }
.sidebar { width: 320px; flex-shrink: 0; }
.main { flex: 1; min-width: 0; }
.field-tree { max-height: 600px; overflow-y: auto; }
.field-group { margin-bottom: 12px; }
.field-group h3 { font-size: 14px; font-weight: 600; color: #555; padding: 6px 0; border-bottom: 1px solid #eee; margin-bottom: 6px; cursor: pointer; user-select: none; }
.field-item { display: flex; align-items: center; gap: 6px; padding: 3px 0 3px 12px; font-size: 13px; }
.field-item input[type=checkbox] { cursor: pointer; }
.field-item label { cursor: pointer; }
.preview-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.preview-table th { background: #fafafa; padding: 8px 6px; text-align: left; font-weight: 600; border-bottom: 2px solid #e8e8e8; white-space: nowrap; position: sticky; top: 0; background: #fafafa; }
.preview-table td { padding: 6px; border-bottom: 1px solid #f0f0f0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }
.preview-table tr:hover td { background: #e6f7ff; }
.export-bar { display: flex; gap: 8px; align-items: center; padding: 12px 0; }
.stat { font-size: 13px; color: #888; }
.htmx-indicator { opacity: 0; transition: opacity .2s; }
.htmx-request .htmx-indicator { opacity: 1; }
.htmx-request.htmx-indicator { opacity: 1; }
.error-msg { color: #ff4d4f; font-size: 13px; padding: 8px; background: #fff2f0; border-radius: 4px; margin: 4px 0; }
.empty-msg { color: #999; text-align: center; padding: 40px; }
.summary-cards { display: flex; gap: 12px; flex-wrap: wrap; margin: 12px 0; }
.summary-card { background: #fafafa; border-radius: 6px; padding: 12px 16px; min-width: 100px; text-align: center; }
.summary-card .num { font-size: 24px; font-weight: 700; color: #1a73e8; }
.summary-card .label { font-size: 12px; color: #888; margin-top: 4px; }
.pagination { display: flex; gap: 8px; align-items: center; justify-content: center; padding: 12px 0; }
.pagination button { padding: 4px 12px; border: 1px solid #d9d9d9; border-radius: 4px; background: #fff; cursor: pointer; }
.pagination button:hover { border-color: #1a73e8; color: #1a73e8; }
.pagination button:disabled { color: #ccc; cursor: not-allowed; }
.footer { text-align: center; color: #999; font-size: 12px; padding: 20px; }
</style>
</head>
<body>
<div class="header">
  <h1>switch-inspector</h1>
  <span>锐捷交换机日志解析 · 交互式字段选择</span>
</div>
<div class="container" x-data="appState()">
  <div class="card">
    <div class="scan-bar">
      <input type="text" id="scanPath" x-model="scanPath" placeholder="日志目录路径, 如 C:\Ruijie\logs\" @keydown.enter="doScan">
      <button class="btn-primary" @click="doScan" :disabled="scanning">
        <span x-show="!scanning">📂 扫描</span>
        <span x-show="scanning">扫描中...</span>
      </button>
    </div>
    <div x-show="error" class="error-msg" x-text="error"></div>
  </div>

  <div x-show="scanned" style="display:none">
    <div class="summary-cards">
      <div class="summary-card"><div class="num" x-text="stats.files"></div><div class="label">日志文件</div></div>
      <div class="summary-card"><div class="num" x-text="stats.devices"></div><div class="label">设备数</div></div>
      <div class="summary-card"><div class="num" x-text="stats.commands"></div><div class="label">命令类型</div></div>
      <div class="summary-card"><div class="num" x-text="stats.fields"></div><div class="label">可用字段</div></div>
    </div>

    <div class="layout">
      <div class="sidebar card">
        <h3 style="margin-bottom:8px">☐ <input type="checkbox" @change="toggleAll" x-model="allChecked"> 全选</h3>
        <div class="field-tree" id="fieldTree">
          <template x-for="(group, cat) in fieldGroups" :key="cat">
            <div class="field-group">
              <h3 @click="toggleGroup(cat)" x-text="groupLabel(cat)"></h3>
              <template x-for="field in group" :key="field.key">
                <div class="field-item">
                  <input type="checkbox" :value="field.key" x-model="selectedFields" :id="'f_'+field.key">
                  <label :for="'f_'+field.key" x-text="field.label"></label>
                </div>
              </template>
            </div>
          </template>
        </div>
      </div>

      <div class="main card">
        <div class="export-bar">
          <span class="stat">共 <b x-text="totalRows"></b> 行</span>
          <button class="btn-success" @click="refreshPreview" :disabled="selectedFields.length===0">预览</button>
          <button class="btn-export" @click="exportCSV" :disabled="selectedFields.length===0">导出 CSV</button>
          <button class="btn-export" @click="exportXLSX" :disabled="selectedFields.length===0">导出 Excel</button>
          <span class="htmx-indicator" x-show="loading">加载中...</span>
        </div>
        <div id="preview" x-show="hasPreview">
          <table class="preview-table">
            <thead>
              <tr>
                <template x-for="col in previewColumns" :key="col">
                  <th x-text="col"></th>
                </template>
              </tr>
            </thead>
            <tbody>
              <template x-for="row in previewRows" :key="row._rowid">
                <tr>
                  <template x-for="col in previewColumns" :key="col">
                    <td x-text="row[col] || ''" :title="row[col] || ''"></td>
                  </template>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
        <div x-show="!hasPreview && scanned" class="empty-msg">勾选左侧字段后点击预览</div>
      </div>
    </div>
  </div>
</div>
<div class="footer">switch-inspector v0.1</div>
<script>
function appState() {
  return {
    scanPath: '',
    scanning: false,
    scanned: false,
    error: '',
    selectedFields: [],
    allChecked: false,
    fieldGroups: {},
    stats: {files:0, devices:0, commands:0, fields:0},
    previewColumns: [],
    previewRows: [],
    totalRows: 0,
    hasPreview: false,
    loading: false,

    toggleAll() {
      if (this.allChecked) {
        const all = Object.values(this.fieldGroups).flat().map(f => f.key);
        this.selectedFields = all;
      } else {
        this.selectedFields = [];
      }
    },
    toggleGroup(cat) {
      const keys = this.fieldGroups[cat].map(f => f.key);
      const allSelected = keys.every(k => this.selectedFields.includes(k));
      if (allSelected) {
        this.selectedFields = this.selectedFields.filter(k => !keys.includes(k));
      } else {
        keys.forEach(k => { if (!this.selectedFields.includes(k)) this.selectedFields.push(k); });
      }
    },
    fieldLabel(cat) {
      const labels = {device:'设备信息', interface:'接口信息', neighbor:'邻居信息', system:'系统信息', log:'系统日志'};
      return labels[cat] || cat;
    },
    groupLabel(cat) {
      const count = this.fieldGroups[cat]?.length || 0;
      const selected = this.fieldGroups[cat]?.filter(f => this.selectedFields.includes(f.key)).length || 0;
      return `${this.fieldLabel(cat)} (${selected}/${count})`;
    },
    async doScan() {
      if (!this.scanPath.trim()) return;
      this.scanning = true;
      this.error = '';
      try {
        const r = await fetch('/api/scan', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path: this.scanPath})});
        const data = await r.json();
        if (data.error) { this.error = data.error; return; }
        this.fieldGroups = data.field_groups;
        this.stats = {files: data.file_count, devices: data.device_count, commands: data.command_count, fields: data.field_count};
        this.scanned = true;
        this.hasPreview = false;
        this.previewRows = [];
        this.selectedFields = [];
        this.allChecked = false;
      } catch(e) { this.error = '扫描失败: ' + e.message; }
      finally { this.scanning = false; }
    },
    async refreshPreview() {
      if (this.selectedFields.length === 0) return;
      this.loading = true;
      try {
        const r = await fetch('/api/preview', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({fields: this.selectedFields, page:1, page_size:100})});
        const data = await r.json();
        this.previewColumns = data.columns;
        this.previewRows = data.rows;
        this.totalRows = data.total;
        this.hasPreview = true;
      } catch(e) { this.error = '预览失败: ' + e.message; }
      finally { this.loading = false; }
    },
    async exportCSV() {
      await this._export('csv');
    },
    async exportXLSX() {
      await this._export('xlsx');
    },
    async _export(fmt) {
      if (this.selectedFields.length === 0) return;
      try {
        const r = await fetch(`/api/export?fields=${this.selectedFields.join(',')}&format=${fmt}`);
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `巡检数据_${new Date().toISOString().slice(0,10)}.${fmt}`;
        a.click();
        URL.revokeObjectURL(url);
      } catch(e) { this.error = '导出失败: ' + e.message; }
    }
  };
}
</script>
</body>
</html>
"""


# --- API routes ---

@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML


@app.post("/api/scan")
async def api_scan(body: dict):
    global logs, parsed_data, catalog
    path = body.get("path", "")
    if not path or not os.path.isdir(path):
        return {"error": f"目录不存在: {path}"}

    log_files = sorted(Path(path).rglob("*.log"))
    if not log_files:
        return {"error": f"在 {path} 中未找到 .log 文件"}

    logs = []
    errors = []
    for lf in log_files:
        try:
            logs.append(split_log_file(str(lf)))
        except Exception as e:
            errors.append(f"{lf.name}: {e}")

    parsed_data = parse_all_logs(logs, registry)

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

    return {
        "file_count": len(log_files),
        "device_count": len(logs),
        "command_count": len(all_cmds),
        "field_count": len(catalog.fields),
        "field_groups": field_groups,
        "warnings": errors[:10],
    }


@app.post("/api/preview")
async def api_preview(body: dict):
    fields = body.get("fields", [])
    page = body.get("page", 1)
    page_size = body.get("page_size", 100)

    field_defs = {f.key: f for f in catalog.fields}
    cat_keys: dict = {}
    for key in fields:
        fd = field_defs.get(key)
        if fd:
            cat_keys.setdefault(fd.category, []).append(key)

    device_rows = parsed_data.get('device', [])

    CAT_PRIORITY = ['interface', 'neighbor', 'device', 'system', 'log']
    primary_cat = next((c for c in CAT_PRIORITY if c in cat_keys), 'interface')

    all_rows = []
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
    field_defs = {f.key: f for f in catalog.fields}
    cat_keys: dict = {}
    for key in field_keys:
        fd = field_defs.get(key)
        if fd:
            cat_keys.setdefault(fd.category, []).append(key)

    device_rows = parsed_data.get('device', [])
    CAT_PRIORITY = ['interface', 'neighbor', 'device', 'system', 'log']
    primary_cat = next((c for c in CAT_PRIORITY if c in cat_keys), 'interface')

    all_rows = []
    all_cat_rows = parsed_data.get(primary_cat, [])
    if primary_cat == 'interface':
        all_cat_rows = merge_interface_rows(all_cat_rows, device_rows)
    elif primary_cat == 'neighbor':
        all_cat_rows = merge_neighbor_rows(all_cat_rows)

    primary_keys = cat_keys.get(primary_cat, [])
    merged = project_rows(all_cat_rows, primary_keys)

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
        merged.extend(extra_rows)

    all_rows = merged

    if format == "xlsx":
        data = export_xlsx(all_rows, catalog.fields, field_keys)
        return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f"attachment; filename=switch_report.xlsx"})
    else:
        data = export_csv(all_rows, catalog.fields, field_keys)
        return Response(content=data, media_type="text/csv; charset=utf-8-sig",
                        headers={"Content-Disposition": "attachment; filename=switch_report.csv"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 9876))
    print(f"  switch-inspector starting at http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
