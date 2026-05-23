# switch-inspector

锐捷交换机巡检日志解析工具。自动扫描 RSSP 巡检系统导出的 .log 文件，交互式选择需要提取的字段，导出结构化表格。

## 快速开始

```bash
pip install -r requirements.txt
python main.py
# 打开 http://127.0.0.1:9876
```

## 使用方法

1. 在 Web 页面输入日志目录路径，点击扫描
2. 勾选需要提取的字段（设备信息/接口信息/邻居信息/系统信息/系统日志）
3. 点击预览查看结果
4. 导出 CSV 或 Excel

## 支持的解析命令 (19个)

| 命令 | 解析策略 | 输出字段数 |
|---|---|---|
| `show version` / `show version detail` | KV 对 | 6-8 |
| `show run` / `show startup-config` | 配置块解析 | 接口VLAN/ACL/模式 |
| `show interfaces description` | 固定宽度表格 | 接口名/状态/管理状态/描述 |
| `show interfaces status` | 固定宽度表格 | 接口名/状态/VLAN/双工/速率/类型 |
| `show interfaces counters errors` | 双表格合并 | 8种错误计数 |
| `show interfaces counters rate up` | 固定宽度表格 | 入/出向速率(bps/pps) |
| `show interfaces usage` | 固定宽度表格 | 带宽/平均利用率/入利用率/出利用率 |
| `show interfaces transceiver manuinfo` | 块分割 | 光模块厂商/型号/版本/日期/在位 |
| `show lldp neighbors detail` | KV 块提取 | 邻居名/IP/端口/型号/ChassisID |
| `show logging` | 日志行解析 | 时间/Facility/级别/内容 |
| `show fan speed` | 固定宽度表格 | 风扇ID/类型/状态/转速 |
| `show clock` | 单值 | 系统时间 |
| `show exception` | 单值 | 异常信息 |
| `show coredump files` | 单值 | CoreDump文件数 |
| `show erps` | 单值 | ERPS状态 |
| `show switch virtual link port` | 单值 | 交换机模式 |
| `show password policy` | KV 对 | 密码策略 |
| `show ip dhcp snooping` | 单值 | DHCP Snooping状态/信任接口数 |

## 架构

```
日志目录/*.log
    │
    ▼ splitter (按 !---cmd 分割 + 文件名/JSON双源元数据)
    │
    ▼ parser registry (自动加载 parsers/*.py)
    │
    ▼ field_catalog (字段发现 + 跨命令 JOIN + 接口名归一化)
    │
    ▼ FastAPI + HTMX Web UI (字段选择 → 预览 → 导出)
```

- **插件化**: `parsers/` 目录下放 .py 文件自动注册，无需修改核心代码
- **TextFSM 可集成**: `pip install ntc-templates textfsm` 启用 TextFSM 引擎（v2.0）

## 项目结构

```
switch-inspector/
├── main.py                 # FastAPI 入口
├── engine/
│   ├── splitter.py         # 文件扫描 + 命令块分割
│   ├── parser_base.py      # FixedWidthTableParser, KVPParser, BlockParser 基类
│   ├── registry.py         # 解析器注册表 + TextFSM 封装
│   ├── field_catalog.py    # 字段聚合 + 跨类别合并
│   ├── normalizer.py       # 接口名归一化 (Gi→GigabitEthernet)
│   └── exporter.py         # CSV/Excel 导出
├── parsers/                # 插件目录，自动发现
│   ├── show_version.py
│   ├── show_run.py
│   ├── show_interfaces_description.py
│   ├── show_interfaces_transceiver.py
│   ├── show_interfaces_counters.py
│   ├── show_interfaces_usage.py
│   ├── show_lldp_neighbors_detail.py
│   ├── show_logging.py
│   ├── show_fan.py
│   └── builtin_single.py
└── requirements.txt
```

## License

MIT
