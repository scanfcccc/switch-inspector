import re
from engine.parser_base import BaseParser, FieldDef, ParseResult
from engine.normalizer import normalize_iface
from typing import Dict, List


class ShowRun(BaseParser):
    command = "show run"
    fields = [
        FieldDef(key="interface", label="接口名", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="vlan", label="VLAN", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="interface_mode", label="接口模式", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="acl_in", label="入方向ACL", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="dhcp_snooping_trust", label="DHCP Snooping信任", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="rldp_action", label="RLDP动作", category="interface",
                 join_group="interface", join_key="normalized_iface"),
        FieldDef(key="storm_control", label="风暴控制", category="interface",
                 join_group="interface", join_key="normalized_iface"),
    ]

    IFACE_PATTERN = re.compile(
        r'^interface\s+(GigabitEthernet|TenGigabitEthernet|Ethernet|'
        r'FastEthernet|AggregatePort|VLAN|Loopback)\s+(\d+(?:/\d+)*(?:/\d+)?)',
        re.IGNORECASE
    )

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        lines = raw.split('\n')
        current_iface = None
        current_config: Dict[str, str] = {}
        in_iface = False

        for line in lines:
            line_stripped = line.strip()

            m = self.IFACE_PATTERN.match(line_stripped)
            if m:
                if current_iface and current_config:
                    result.rows.append(self._build_row(current_iface, current_config))
                full_name = f"{m.group(1)} {m.group(2)}"
                current_iface = normalize_iface(full_name)
                current_config = {}
                in_iface = True
                continue

            if line_stripped.startswith('!') and not line_stripped.startswith('!---'):
                if in_iface and current_iface:
                    result.rows.append(self._build_row(current_iface, current_config))
                    current_iface = None
                    current_config = {}
                in_iface = False
                continue

            if in_iface and current_iface:
                self._parse_config_line(line_stripped, current_config)

        if current_iface and current_config:
            result.rows.append(self._build_row(current_iface, current_config))

        return result

    def _parse_config_line(self, line: str, config: Dict[str, str]):
        if line.startswith('switchport access vlan'):
            config['vlan'] = line.split()[-1]
            if 'mode' not in config:
                config['mode'] = 'access'
        elif 'switchport mode trunk' in line:
            config['mode'] = 'trunk'
        elif line.startswith('ip access-group'):
            parts = line.split()
            if len(parts) >= 4:
                config['acl_in'] = parts[2]
        elif 'ip dhcp snooping trust' in line:
            config['dhcp_snooping_trust'] = 'trust'
        elif line.startswith('rldp port loop-detect'):
            parts = line.split()
            if len(parts) >= 5:
                config['rldp'] = parts[4]
        elif line.startswith('storm-control'):
            config['storm_control'] = 'yes'

    def _build_row(self, iface: str, config: Dict[str, str]) -> Dict:
        return {
            'interface': iface,
            'normalized_iface': iface,
            'vlan': config.get('vlan', 'trunk' if config.get('mode') == 'trunk' else 'N/A'),
            'interface_mode': config.get('mode', 'N/A'),
            'acl_in': config.get('acl_in', ''),
            'dhcp_snooping_trust': '是' if config.get('dhcp_snooping_trust') else '否',
            'rldp_action': config.get('rldp', ''),
            'storm_control': config.get('storm_control', '否'),
            'category': 'interface',
        }
