# Handoff: switch-inspector

## 项目状态

锐捷交换机巡检日志解析工具。v2.0 已发布，核心功能完整。

**仓库**: `https://github.com/scanfcccc/switch-inspector`
**本地**: `C:\Users\happy\Desktop\dev\switch-inspector`

## 已完成

- [x] 引擎: splitter → parser registry → field_catalog → exporter
- [x] 21个 Python 自定义解析器覆盖全部常用 show 命令
- [x] ntc-templates 集成架构 (TextFSM 引擎就绪，未启用——用户未装库)
- [x] DDM 光功率解析器 (复用了 v5 正则在 parsers/show_interfaces_transceiver_diagnosis.py)
- [x] 接口名归一化 (Gi/Te/TF/Twe/Fo/Hu → 完整名称)
- [x] FastAPI + HTMX Web UI (字段选择 → 预览 → 导出)
- [x] 跨类别行标签 (_row_type: interface/neighbor/system/log)
- [x] FieldDef key 与数据 key 一致性检查
- [x] 5 型号 277 文件测试通过
- [x] 已推送到 GitHub

## 关键架构决策

1. **解析优先级**: ntc-templates TextFSM 优先, Python 自定义补充, 原始文本兜底
2. **字段聚合**: 按 normalized_iface + device_ip JOIN，device字段自动注入
3. **多类别显示**: 每行带 `_row_type` 标签, CSV 第一列 `数据类型`

## 未完成 (v2.0 之后)

- [ ] ntc-templates 安装启用 (用户需 `pip install ntc-templates textfsm`)
- [ ] ruijie-templates 的 40+ TextFSM 模板合并
- [ ] 更多缺失解析器: show poe, show memory, show cpu, show temperature
- [ ] Excel 多 sheet 导出 (按类别分表)
- [ ] 预览 UI 里按 `_row_type` 分组展示/筛选
- [ ] 跨平台打包 (pyinstaller 单 exe)
- [ ] 全量 277 文件的性能基准测试

## 已修复的 Bug

1. BlockParser: `\s` 跨行匹配, 改用 `[ \t]` + `[^=\n]`
2. KVPParser: 过滤正则误杀 KVP 行 (加了 `$` 锚定)
3. FixedWidthTableParser: 用分隔线列宽定位而非空格分裂
4. FieldDef key vs 数据 key 不同步 (show_fan, show_interfaces_transceiver)
5. normalizer: 添加 TFGigabitEthernet 前缀
6. neighbors: 端口 ID 为 MAC 地址时的直通处理

## 建议下会话加载的技能

- `handoff` (压缩本文档)
- `diagnose` (如需排查新的解析问题)
- `tdd` (如需添加新解析器)
