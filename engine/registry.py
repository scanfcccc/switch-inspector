import importlib
import inspect
import pkgutil
from typing import Dict, List, Optional

from engine.parser_base import BaseParser, FieldDef, ParseResult
from engine.normalizer import normalize_iface

# TextFSM 命令→模板映射表
# 格式: (命令名, 模板名, 默认类别, JOIN组, JOIN键)
TEMPLATE_MAP: Dict[str, tuple] = {
    "show version":                     ("ruijie_os_show_version",               "device",    "device",   "device_ip"),
    "show clock":                       ("ruijie_os_show_clock",                 "device",    "device",   "device_ip"),
    "show version slots":               ("ruijie_os_show_version_slots",         "device",    "device",   "device_ip"),
    "show manuinfo":                    ("ruijie_os_show_manuinfo",              "device",    "device",   "device_ip"),
    "show interfaces description":      ("ruijie_os_show_interfaces_description", "interface","interface","normalized_iface"),
    "show interfaces transceiver":      ("ruijie_os_show_interfaces_transceiver", "interface","interface","normalized_iface"),
    "show interfaces status":           ("ruijie_os_show_interfaces_status",     "interface", "interface","normalized_iface"),
    "show vlan":                        ("ruijie_os_show_vlan",                  "interface", "interface","normalized_iface"),
    "show logging":                     ("ruijie_os_show_logging",               "log",       None,       None),
    "show lldp neighbors detail":       ("ruijie_os_show_lldp_neighbors_detail", "neighbor",  "neighbor", "local_iface"),
    "show fan speed":                   ("ruijie_os_show_fan",                   "system",    "device",   "device_ip"),
    "show aggregatePort summary":       ("ruijie_os_show_aggregatePort_summary", "interface", "interface","normalized_iface"),
    "show interfaces counters rate":    ("ruijie_os_show_interfaces_counters_rate","interface","interface","normalized_iface"),
    "show vrrp":                        ("ruijie_os_show_vrrp",                  "interface", "interface","normalized_iface"),
    "show arp":                         ("ruijie_os_show_arp",                   "interface", "interface","normalized_iface"),
    "show mac-address-table":           ("ruijie_os_show_mac-address-table",     "interface", "interface","normalized_iface"),
    "show ip interface brief":          ("ruijie_os_show_ip_interface_brief",    "interface", "interface","normalized_iface"),
    "show ip route":                    ("ruijie_os_show_ip_route",              "device",    "device",   "device_ip"),
    "show interfaces switchport":       ("ruijie_os_show_interfaces_switchport", "interface", "interface","normalized_iface"),
    "show interfaces":                  ("ruijie_os_show_interfaces",            "interface", "interface","normalized_iface"),
}

# 字段标签映射 (TextFSM 原始 key → 中文标签)
FIELD_LABELS = {
    "interface": "接口名", "port": "端口", "vlan": "VLAN", "vlan_id": "VLAN ID",
    "status": "状态", "admin_status": "管理状态", "duplex": "双工模式", "speed": "速率",
    "description": "描述", "type": "类型", "mac_address": "MAC地址",
    "ip_address": "IP地址", "prefix": "前缀", "protocol": "协议",
    "neighbor": "邻居设备", "neighbor_interface": "邻居端口",
    "chassis_id": "ChassisID", "system_name": "系统名称",
    "software_version": "软件版本", "hardware_version": "硬件版本",
    "serial_number": "序列号", "model": "型号",
    "uptime": "运行时间", "clock": "系统时间",
    "fan": "风扇", "power": "电源", "temperature": "温度",
    "log": "日志内容", "facility": "日志设施", "severity": "日志级别",
    "timestamp": "时间戳", "message": "消息",
    "count": "计数", "rate": "速率",
    "errdisabled": "错误禁用", "reason": "原因",
}


class ParserRegistry:
    def __init__(self):
        self._textfsm_enabled = False
        self._textfsm_parsers: Dict[str, TextFSMWrapper] = {}
        self._custom_parsers: Dict[str, BaseParser] = {}

    def register_textfsm(self, wrapper: "TextFSMWrapper"):
        self._textfsm_parsers[wrapper.command] = wrapper

    def register_custom(self, parser: BaseParser):
        self._custom_parsers[parser.command] = parser

    def has(self, command: str) -> bool:
        return command in self._textfsm_parsers or command in self._custom_parsers

    def all_fields(self) -> List[FieldDef]:
        seen = set()
        fields = []
        for p in self._textfsm_parsers.values():
            for f in p.fields:
                if f.key not in seen:
                    seen.add(f.key)
                    fields.append(f)
        for p in self._custom_parsers.values():
            for f in p.fields:
                if f.key not in seen:
                    seen.add(f.key)
                    fields.append(f)
        return fields

    def parse(self, command: str, raw: str) -> Optional[ParseResult]:
        result = None

        # 1. ntc-templates TextFSM (优先)
        if self._textfsm_enabled and command in self._textfsm_parsers:
            try:
                result = self._textfsm_parsers[command].parse(raw)
                if result and result.rows:
                    return result
            except Exception as e:
                result = ParseResult(errors=[f"TextFSM failed: {e}"])

        # 2. Python 自定义解析器 (补充)
        if command in self._custom_parsers:
            result = self._custom_parsers[command].parse(raw)
            if result and result.rows:
                return result

        # 3. 返回 None (调用方做兜底)
        return result

    def resolve(self, command: str, raw: str) -> ParseResult:
        """强制返回 ParseResult，无法解析时返回空行"""
        result = self.parse(command, raw)
        if result is None:
            return ParseResult()
        return result

    def load_custom_parsers(self):
        from parsers import __path__ as parsers_paths
        for importer, modname, ispkg in pkgutil.iter_modules(parsers_paths):
            if modname.startswith('_'):
                continue
            try:
                module = importlib.import_module(f"parsers.{modname}")
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and issubclass(obj, BaseParser)
                            and obj is not BaseParser and hasattr(obj, 'command')
                            and obj.command):
                        instance = obj()
                        self.register_custom(instance)
            except Exception as e:
                print(f"Failed to load parser {modname}: {e}")

    def load_textfsm_parsers(self):
        try:
            from ntc_templates import parse_output
            self._textfsm_enabled = True
        except ImportError:
            print("ntc-templates not installed, TextFSM engine disabled")
            return

        for cmd, (tmpl, category, join_group, join_key) in TEMPLATE_MAP.items():
            wrapper = TextFSMWrapper(cmd, tmpl, category, join_group, join_key)
            self.register_textfsm(wrapper)

    def initialize(self):
        """初始化: 先加载 TextFSM, 再加载 Python 解析器(只覆盖 TextFSM 没覆盖的命令)"""
        self.load_textfsm_parsers()
        self.load_custom_parsers()

        overlap = set(self._textfsm_parsers.keys()) & set(self._custom_parsers.keys())
        if overlap:
            print(f"Custom parsers override TextFSM for: {overlap}")


class TextFSMWrapper(BaseParser):
    def __init__(self, command: str, template_name: str,
                 default_category: str = "interface",
                 join_group: str = None, join_key: str = None):
        self.command = command
        self._tmpl = template_name
        self._default_category = default_category
        self._join_group = join_group
        self._join_key = join_key
        self.fields = []

    def _infer_category(self, key: str) -> str:
        k = key.lower()
        if any(x in k for x in ['neighbor', 'chassis', 'system_name', 'mgmt_addr']):
            return 'neighbor'
        if any(x in k for x in ['fan', 'power_supply', 'temperature', 'coredump']):
            return 'system'
        if any(x in k for x in ['log', 'message', 'facility', 'severity', 'seq']):
            return 'log'
        if self._default_category:
            return self._default_category
        return 'device'

    def _infer_join_group(self, key: str) -> Optional[str]:
        k = key.lower()
        if any(x in k for x in ['neighbor', 'chassis', 'system_name']):
            return 'neighbor'
        if any(x in k for x in ['interface', 'port', 'vlan']) and 'neighbor' not in k:
            return 'interface'
        return self._join_group

    def _infer_join_key(self, key: str) -> Optional[str]:
        kg = self._infer_join_group(key)
        if kg == 'interface':
            return 'normalized_iface'
        if kg == 'neighbor':
            return 'local_iface'
        return None

    def parse(self, raw: str) -> Optional[ParseResult]:
        try:
            from ntc_templates import parse_output
            rows = parse_output(platform="ruijie_os",
                                 command=self.command,
                                 data=raw)
        except Exception as e:
            return ParseResult(errors=[f"TextFSM {self.command}: {e}"])

        if not isinstance(rows, list) or not rows:
            return ParseResult(errors=[f"TextFSM {self.command}: empty result"])

        # 构建字段定义 (仅首次)
        if not self.fields:
            self.fields = []
            for k in rows[0].keys():
                cat = self._infer_category(k)
                jg = self._infer_join_group(k)
                jk = self._infer_join_key(k)
                label = FIELD_LABELS.get(k.lower(), k)
                self.fields.append(FieldDef(
                    key=k, label=label, category=cat,
                    join_group=jg, join_key=jk,
                ))

        # 归一化接口名
        has_iface = any('interface' in k.lower() for k in rows[0] if k != 'neighbor_interface')
        for row in rows:
            for k in row:
                if k.lower() == 'interface' and '/' in str(row[k]):
                    row['normalized_iface'] = normalize_iface(str(row[k]))
                    break
                if k.lower() == 'port' and '/' in str(row[k]):
                    row['normalized_iface'] = normalize_iface(str(row[k]))
                    break
            row['_origin'] = 'textfsm'

        return ParseResult(rows=rows)
