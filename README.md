# switch-inspector v2.0

锐捷交换机巡检日志解析工具。自动扫描 RSSP 巡检系统导出的 .log 文件，交互式选择需要提取的字段，导出结构化表格。

## 快速开始

```bash
pip install -r requirements.txt
python main.py
# 打开 http://127.0.0.1:9876
```

可选启用 TextFSM 引擎（覆盖更多命令）：
```bash
pip install ntc-templates textfsm
# 重启即可，自动生效
```

## 使用方法

1. 在 Web 页面输入日志目录路径，点击扫描
2. 勾选需要提取的字段（设备信息/接口信息/邻居信息/系统信息/系统日志/DDM光功率）
3. 点击预览查看结果
4. 导出 CSV 或 Excel

## 解析引擎 (v2.0)

双层架构，按优先级自动选择：

```
TextFSM 引擎 (ntc-templates + ruijie-templates)
  覆盖 21 个通用 show 命令
  └─ 失败时降级
Python 自定义解析器
  覆盖 TextFSM 无法处理的场景:
  - show run 配置块解析 (接口VLAN/ACL/模式)
  - show interfaces transceiver manuinfo 块分割
  - show interfaces counters errors 双表格合并
  - DDM 光功率诊断 (show interfaces transceiver diagnosis)
  - show logging 系统日志结构化
```

**启用 TextFSM 引擎后命令覆盖从 21 提升至 40+。**

## 支持的解析命令 (21个自定义 + 21个TextFSM)

### Python 自定义解析器 (21个)
| 命令 | 主要输出字段 |
|---|---|
| `show version` / `show version detail` | 型号/序列号/软件版本/运行时长 |
| `show run` / `show startup-config` | 接口VLAN/ACL入方向/风暴控制/RLDP/DHCP Snooping |
| `show interfaces description` | 接口名/状态/管理状态/描述 |
| `show interfaces status` | 接口名/状态/VLAN/双工/速率/类型 |
| `show interfaces counters errors` | UnderSize/OverSize/CRC/FCS等8种 |
| `show interfaces counters rate up` | 入/出向速率(bps/pps) |
| `show interfaces usage` | 带宽/平均利用率/入利用率/出利用率 |
| `show interfaces transceiver manuinfo` | 光模块厂商/型号/版本/生产日期/在位 |
| `show interfaces transceiver diagnosis` | **温度/电压/偏置电流/RX光功率/TX光功率** |
| `show lldp neighbors detail` | 邻居设备名/IP/端口/型号/ChassisID |
| `show logging` | 时间/Facility/级别/日志内容 |
| `show fan speed` | 风扇ID/类型/状态/转速 |
| `show clock` | 系统时间 |
| `show exception` | 异常信息 |
| `show coredump files` | CoreDump文件数 |
| `show erps` | ERPS状态 |
| `show switch virtual link port` | 交换机模式(独立/虚拟化) |
| `show password policy` | 密码加密/强密码/最小长度 |
| `show ip dhcp snooping` | DHCP Snooping启用/信任接口数 |

### TextFSM 模板 (ntc-templates + ruijie-templates, 可选启用)
`show version` `show clock` `show vlan` `show arp` `show mac-address-table`
`show ip route` `show ip interface brief` `show interfaces` `show interfaces switchport`
`show interfaces transceiver` `show aggregatePort summary` `show vrrp`
`show manuinfo` `show version slots` `show fan` 等

## 架构

```
日志目录/*.log
    │
    ▼ splitter (按 !---cmd 分割 + 文件名/JSON双源元数据)
    │
    ▼ Parser Registry (v2.0: TextFSM优先 → Python补充)
    │    ├─ ntc-templates TextFSM (ruijie_os 平台)
    │    └─ parsers/*.py (自定义解析器)
    │
    ▼ field_catalog (字段发现 + 跨命令 JOIN + 接口名归一化)
    │
    ▼ FastAPI + HTMX Web UI (字段选择 → 预览 → 导出)
```

- **插件化**: `parsers/` 目录下放 .py 文件自动注册
- **TextFSM 集成**: `load_textfsm_parsers()` 自动加载 ntc-templates 模板
- **优先级**: TextFSM → Python自定义 → 原始文本兜底

## 接口名归一化

不同命令输出的接口名格式不一致，工具自动统一：

| 来源 | 原始格式 | 归一化后 |
|---|---|---|
| show interfaces description | `GigabitEthernet 0/1` | `GigabitEthernet 0/1` |
| show interfaces counters errors | `Gi0/1` | `GigabitEthernet 0/1` |
| show lldp neighbors detail | `Te0/25` | `TenGigabitEthernet 0/25` |
| show run | `interface GigabitEthernet 0/1` | `GigabitEthernet 0/1` |

## 项目结构

```
switch-inspector/
├── main.py                 # FastAPI 入口
├── engine/
│   ├── splitter.py         # 文件扫描 + 命令块分割
│   ├── parser_base.py      # FixedWidthTableParser, KVPParser, BlockParser 基类
│   ├── registry.py         # v2.0: 双层解析器注册表 (TextFSM + Custom)
│   ├── field_catalog.py    # 字段聚合 + 跨类别合并
│   ├── normalizer.py       # 接口名归一化
│   └── exporter.py         # CSV/Excel 导出
├── parsers/                # 插件目录，自动发现
│   ├── show_version.py
│   ├── show_run.py
│   ├── show_interfaces_description.py
│   ├── show_interfaces_transceiver.py
│   ├── show_interfaces_transceiver_diagnosis.py  # DDM 光功率
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
