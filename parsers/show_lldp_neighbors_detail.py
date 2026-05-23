import re
from engine.parser_base import BaseParser, FieldDef, ParseResult
from engine.normalizer import normalize_iface, normalize_port_id


class ShowLldpNeighborsDetail(BaseParser):
    command = "show lldp neighbors detail"
    fields = [
        FieldDef(key="interface", label="本端接口", category="neighbor",
                 join_group="neighbor", join_key="local_iface"),
        FieldDef(key="neighbor_name", label="邻居设备名", category="neighbor"),
        FieldDef(key="neighbor_ip", label="邻居IP", category="neighbor"),
        FieldDef(key="neighbor_interface", label="邻居端口", category="neighbor"),
        FieldDef(key="neighbor_model", label="邻居型号", category="neighbor"),
        FieldDef(key="neighbor_chassis_id", label="邻居ChassisID", category="neighbor"),
    ]

    def parse(self, raw: str) -> ParseResult:
        result = ParseResult()
        # split on "LLDP neighbor-information of port" lines
        sections = re.split(
            r'(?=\n-{3,}\n.*?LLDP neighbor-information of port)',
            raw
        )

        for section in sections:
            section = section.strip()
            if 'LLDP neighbor-information' not in section:
                continue

            row = {'category': 'neighbor'}
            for line in section.split('\n'):
                line = line.strip()
                if not line or all(c in '-=' for c in line.strip()):
                    continue

                m = re.search(r'port \[([^\]]+)\]', line, re.IGNORECASE)
                if m:
                    row['interface'] = normalize_iface(m.group(1))
                    continue

                if ':' not in line:
                    continue

                k, v = line.split(':', 1)
                k = k.strip()
                v = v.strip()
                if not v:
                    continue

                if 'System name' == k:
                    row['neighbor_name'] = v
                elif 'System description' in k:
                    model_m = re.search(r'\(([\w-]+)\)', v)
                    row['neighbor_model'] = model_m.group(1) if model_m else v.split(',')[0]
                elif k == 'Management address' and '.' in v:
                    row['neighbor_ip'] = v
                elif k == 'Port ID' and v:
                    row['neighbor_interface'] = normalize_port_id(v)
                elif k == 'Chassis ID' and '.' in v:
                    row['neighbor_chassis_id'] = v

            if 'interface' in row:
                row['local_iface'] = row['interface']
                result.rows.append(row)

        return result
